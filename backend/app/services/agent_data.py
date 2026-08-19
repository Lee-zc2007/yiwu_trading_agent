"""面向 Agent 的只读业务数据网关实现。

数据库访问被限制在普通业务服务层中，``backend.app.agent`` 不导入 ORM、模型或
Session。这里负责把现有业务能力封装成只读 DTO；订单分析只会复用已有风控服务，
且强制关闭风险事件持久化。若客户没有已保存的信用评分，则拒绝分析，避免风控服务
的兜底路径间接创建新评分。
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.security import mask_email, mask_phone
from ..models import Customer, RiskEvent, Transaction, TransactionTimelineEvent
from ..repositories.customers import CustomerRepository
from ..risk.decision import TransactionDecisionService
from ..risk.methodology import RiskEvaluationCriteriaService
from ..risk.service import RiskAssessmentService
from .knowledge_base import KnowledgeBaseService


def model_dict(item) -> dict:
    """将 ORM 实体转换为普通字典，阻止 ORM 对象泄漏到 Agent 层。"""

    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


class SqlAlchemyAgentDataGateway:
    """AgentDataGateway 的 SQLAlchemy 实现，只提供商户隔离的只读查询。"""

    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id
        self.customers = CustomerRepository(db, merchant_id)

    def get_customer_profile(self, customer_id: int | None = None, query: str = "") -> dict | None:
        if customer_id:
            customer = self.customers.get(customer_id)
        elif query.strip():
            customer = next(iter(self.customers.list(search=query.strip())), None)
        else:
            customer = None
        if not customer:
            return None
        # Agent 解释不需要完整联系方式，DTO 默认只暴露脱敏值。
        return {
            "customer_id": customer.id,
            "company_name": customer.company_name,
            "contact_name": customer.name,
            "country": customer.country,
            "region": customer.region,
            "industry": customer.industry,
            "cooperation_start_date": customer.cooperation_start_date,
            "identity_verified": customer.identity_verified,
            "registration_number": customer.registration_number,
            "main_product_category": customer.main_product_category,
            "email": mask_email(customer.email),
            "phone": mask_phone(customer.phone),
        }

    def get_latest_credit_score(self, customer_id: int) -> dict | None:
        # 只读历史表；严禁调用 CreditScoringService.calculate/ latest_or_calculate。
        if not self.customers.get(customer_id):
            return None
        score = self.customers.latest_score(customer_id)
        if not score:
            return None
        data = {
            "id": score.id,
            "customer_id": score.customer_id,
            "total_score": score.total_score,
            "performance_score": score.performance_score,
            "stability_score": score.stability_score,
            "dispute_score": score.dispute_score,
            "identity_score": score.identity_score,
            "relationship_score": score.relationship_score,
            "risk_level": score.risk_level,
            "confidence_level": score.confidence_level,
            "rule_version": score.rule_version,
            "calculated_at": score.calculated_at,
        }
        # 历史表当前没有单独保存自然语言原因，因此仅把已保存的分项事实格式化为说明；
        # 这里不重新计算任何分数，也不推导新的风险等级。
        data["reasons"] = [
            f"履约表现分：{score.performance_score:.1f}",
            f"交易稳定分：{score.stability_score:.1f}",
            f"纠纷控制分：{score.dispute_score:.1f}",
            f"身份可信分：{score.identity_score:.1f}",
            f"合作关系分：{score.relationship_score:.1f}",
        ]
        return data

    def get_customer_transactions(self, customer_id: int, limit: int = 10) -> dict | None:
        if not self.customers.get(customer_id):
            return None
        scope = self.db.query(Transaction).filter(
            Transaction.merchant_id == self.merchant_id,
            Transaction.customer_id == customer_id,
        )
        count, total, average = scope.with_entities(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount), 0.0),
            func.coalesce(func.avg(Transaction.amount), 0.0),
        ).one()
        rows = (
            scope
            .order_by(Transaction.order_time.desc())
            .limit(max(1, min(limit, 50)))
            .all()
        )
        trend_rows = scope.order_by(Transaction.order_time.desc()).limit(12).all()
        return {
            "customer_id": customer_id,
            "transaction_count": int(count),
            "average_order_amount": round(float(average), 2),
            "total_transaction_amount": round(float(total), 2),
            "recent_transactions": [self._transaction_dto(item) for item in rows],
            "transaction_trend": [
                {"order_id": item.id, "order_time": item.order_time, "amount": item.amount}
                for item in reversed(trend_rows)
            ],
        }

    def analyze_order_risk(self, order_id: int) -> dict | None:
        """调用现有规则、异常检测和评分结果，执行不落库的订单分析。"""

        transaction = (
            self.db.query(Transaction)
            .filter(Transaction.id == order_id, Transaction.merchant_id == self.merchant_id)
            .first()
        )
        if not transaction:
            return None
        customer = self.customers.get(transaction.customer_id)
        if not customer:
            return None
        # 必须已有评分：防止 RiskAssessmentService.latest_or_calculate 进入补算路径。
        if not self.customers.latest_score(customer.id):
            raise LookupError("该外商没有已保存的信用评分，无法执行只读订单风控分析")
        result = RiskAssessmentService(self.db, self.merchant_id).analyze_order(
            customer,
            model_dict(transaction),
            transaction.id,
            persist_event=False,
        )
        abnormal_reasons = result.pop("main_reasons", [])
        return {**result, "abnormal_reasons": abnormal_reasons, "analysis_source": "runtime_read_only"}

    def list_risk_alerts(self, customer_id: int | None = None, limit: int = 10) -> dict:
        query = self.db.query(RiskEvent).filter(RiskEvent.merchant_id == self.merchant_id)
        if customer_id:
            if not self.customers.get(customer_id):
                raise LookupError("外商不存在或不属于当前商户")
            query = query.filter(RiskEvent.customer_id == customer_id)
        total = query.count()
        rows = query.order_by(RiskEvent.risk_score.desc(), RiskEvent.created_at.desc()).limit(max(1, min(limit, 50))).all()
        return {"total": total, "items": [self._risk_event_dto(item) for item in rows]}

    def compare_customers(self, customer_id_a: int, customer_id_b: int) -> dict | None:
        """汇总两个外商的既有事实，不在 Agent Tool 中做统计或风险判断。"""

        customers: list[dict] = []
        for customer_id in (customer_id_a, customer_id_b):
            profile = self.get_customer_profile(customer_id)
            if not profile:
                return None
            credit = self.get_latest_credit_score(customer_id)
            transactions = self.get_customer_transactions(customer_id, 5)
            alerts = self.list_risk_alerts(customer_id, 5)
            alert_items = alerts["items"]
            customers.append({
                "customer_id": customer_id,
                "company_name": profile["company_name"],
                "country": profile["country"],
                "identity_verified": profile["identity_verified"],
                "credit_score": credit["total_score"] if credit else None,
                "credit_risk_level": credit["risk_level"] if credit else None,
                "credit_confidence": credit["confidence_level"] if credit else None,
                "transaction_count": transactions["transaction_count"] if transactions else 0,
                "average_order_amount": transactions["average_order_amount"] if transactions else 0.0,
                "total_transaction_amount": transactions["total_transaction_amount"] if transactions else 0.0,
                "risk_alert_count": alerts["total"],
                "highest_alert_score": max((item["risk_score"] for item in alert_items), default=None),
                "highest_alert_level": alert_items[0]["risk_level"] if alert_items else None,
            })
        return {
            "customer_ids": [customer_id_a, customer_id_b],
            "customers": customers,
            "comparison_dimensions": ["信用评分", "身份认证", "交易规模", "历史风险预警"],
        }

    def generate_verification_checklist(self, customer_id: int) -> dict | None:
        """根据已保存风险事件生成确定性人工核验事项。"""

        profile = self.get_customer_profile(customer_id)
        if not profile:
            return None
        alerts = self.list_risk_alerts(customer_id, 20)
        alert_items = alerts["items"]
        rule_codes = {
            rule.get("rule_code")
            for event in alert_items
            for rule in event.get("triggered_rules", [])
            if rule.get("rule_code")
        }
        items = [
            {"code": "CONTACT_RECHECK", "item": "通过原登记联系方式二次确认付款与收货信息", "priority": "high", "basis": "基础人工核验"},
            {"code": "REGISTRATION_CHECK", "item": "核验企业注册号、受益人及认证材料", "priority": "high", "basis": "基础人工核验"},
            {"code": "ACCOUNT_MATCH", "item": "确认付款账户主体与合同主体一致", "priority": "high", "basis": "基础人工核验"},
            {"code": "ADDRESS_CHECK", "item": "发货前复核收货国家、最终地址及签收主体", "priority": "medium", "basis": "基础人工核验"},
        ]
        if "PAYMENT_CHANGED" in rule_codes:
            items.append({"code": "PAYMENT_CHANGE_PROOF", "item": "书面说明付款方式变更原因并验证新账户", "priority": "high", "basis": "PAYMENT_CHANGED"})
        if {"AMOUNT_SURGE", "AMOUNT_ZSCORE", "SMALL_TO_LARGE", "SPLIT_ORDERS"} & rule_codes:
            items.append({"code": "LARGE_ORDER_REVIEW", "item": "复核大额订单资金来源、定金比例和分阶段交付方案", "priority": "high", "basis": "订单金额异常规则"})
        if {"COUNTRY_CHANGED", "ADDRESS_VOLATILITY"} & rule_codes:
            items.append({"code": "LOGISTICS_RECHECK", "item": "核实变更后的收货国家、地址及货代关系", "priority": "high", "basis": "物流信息异常规则"})
        if "CONSECUTIVE_ADVERSE" in rule_codes:
            items.append({"code": "ADVERSE_CASE_CLEARANCE", "item": "核清历史逾期、退款和纠纷的处理结果", "priority": "high", "basis": "CONSECUTIVE_ADVERSE"})
        level_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        highest_level = max(
            (item["risk_level"] for item in alert_items),
            key=lambda value: level_order.get(value, 0),
            default="none",
        )
        return {
            "customer_id": customer_id,
            "company_name": profile["company_name"],
            "highest_risk_level": highest_level,
            "based_on_alert_count": alerts["total"],
            "risk_event_ids": [item["id"] for item in alert_items],
            "items": items,
        }

    def get_risk_event_detail(self, event_id: int) -> dict | None:
        event = self.db.query(RiskEvent).filter(RiskEvent.id == event_id, RiskEvent.merchant_id == self.merchant_id).first()
        return self._risk_event_dto(event) if event else None

    def search_risk_knowledge(self, query: str, category: str | None = None, limit: int = 5) -> dict:
        """查询非结构化知识；与上面的客户、交易 SQL 查询保持物理边界。"""

        return KnowledgeBaseService(self.db).search(query=query, category=category, limit=limit)

    def get_risk_evaluation_criteria(self) -> dict:
        """读取当前生效的系统评价标准；不计算任何具体客户或交易风险。"""

        return RiskEvaluationCriteriaService(self.db).get()

    def _decision_scope(self, customer_id: int | None, transaction_id: int | None):
        transaction = None
        customer = None
        if transaction_id is not None:
            transaction = self.db.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.merchant_id == self.merchant_id,
            ).first()
            if transaction is None:
                raise LookupError("交易不存在或不属于当前商户")
            customer = transaction.customer
            if customer_id is not None and customer.id != customer_id:
                raise LookupError("客户与交易不匹配")
        elif customer_id is not None:
            customer = self.customers.get(customer_id)
            if customer is None:
                raise LookupError("外商不存在或不属于当前商户")
        return customer, transaction

    def evaluate_transaction_decision(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict:
        """调用统一确定性决策服务；不持久化快照，不修改交易。"""

        customer, transaction = self._decision_scope(customer_id, transaction_id)
        return TransactionDecisionService(self.db, self.merchant_id).evaluate(
            transaction_context=transaction_context,
            customer=customer,
            transaction=transaction,
            persist_snapshot=False,
        )

    def get_transaction_risk(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict:
        return self.evaluate_transaction_decision(transaction_context, customer_id, transaction_id)["transaction_risk"]

    def calculate_risk_exposure(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict:
        return self.evaluate_transaction_decision(transaction_context, customer_id, transaction_id)["risk_exposure"]

    def get_evidence_completeness(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict:
        return self.evaluate_transaction_decision(transaction_context, customer_id, transaction_id)["evidence"]

    def evaluate_credit_terms(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict:
        return self.evaluate_transaction_decision(transaction_context, customer_id, transaction_id)

    def simulate_transaction_adjustment(self, base_context: dict, adjustments: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict:
        customer, transaction = self._decision_scope(customer_id, transaction_id)
        return TransactionDecisionService(self.db, self.merchant_id).simulate(
            base_context=base_context,
            adjustments=adjustments,
            customer=customer,
            transaction=transaction,
        )

    def get_transaction_timeline(self, transaction_id: int) -> dict | None:
        transaction = self.db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.merchant_id == self.merchant_id,
        ).first()
        if transaction is None:
            return None
        rows = self.db.query(TransactionTimelineEvent).filter(
            TransactionTimelineEvent.transaction_id == transaction_id,
            TransactionTimelineEvent.merchant_id == self.merchant_id,
        ).order_by(TransactionTimelineEvent.event_time).all()
        return {
            "transaction_id": transaction_id,
            "items": [model_dict(item) for item in rows],
        }

    @staticmethod
    def _transaction_dto(item: Transaction) -> dict:
        return {
            "order_id": item.id,
            "order_number": item.order_number,
            "product_category": item.product_category,
            "product_name": item.product_name,
            "amount": item.amount,
            "currency": item.currency,
            "order_time": item.order_time,
            "payment_method": item.payment_method,
            "final_payment_status": item.final_payment_status,
            "refund_status": item.refund_status,
            "dispute_status": item.dispute_status,
            "overdue_days": item.overdue_days,
            "shipping_country": item.shipping_country,
        }

    @staticmethod
    def _risk_event_dto(item: RiskEvent) -> dict:
        return {
            "id": item.id,
            "customer_id": item.customer_id,
            "order_id": item.order_id,
            "risk_type": item.risk_type,
            "risk_level": item.risk_level,
            "risk_score": item.risk_score,
            "title": item.title,
            "description": item.description,
            "triggered_rules": item.triggered_rules or [],
            "evidence": item.evidence or {},
            "status": item.status,
            "created_at": item.created_at,
        }
