"""三分钟路演编排服务。

演示数据在每次请求内写入临时 SQLite 内存库，并复用正式规则引擎、异常检测、
风控服务和 Agent Tool。请求结束后内存库销毁，因此不会新增或修改真实客户、
订单、评分、预警和会话。非结构化知识检索只读正式 knowledge_base。
"""

from datetime import UTC, date, datetime, timedelta
from statistics import mean

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..agent.graph import AgentDecisionGraph
from ..agent.tools import AgentToolRegistry
from ..core.config import settings
from ..core.database import Base
from ..data.seed import RULE_CONFIGS
from ..models import CreditScoreHistory, Customer, Merchant, RiskEvent, RiskRuleConfig, Transaction
from ..risk.service import RiskAssessmentService
from .agent_data import SqlAlchemyAgentDataGateway, model_dict
from .knowledge_base import KnowledgeBaseService


ROADSHOW_CUSTOMER_ID = 9001
ROADSHOW_ORDER_ID = 9009
ROADSHOW_ORDER_NUMBER = "DEMO-ROADSHOW-200K"


class _RoadshowGateway:
    """结构化数据走临时 SQL，非结构化知识走正式 RAG 的组合网关。"""

    def __init__(self, structured: SqlAlchemyAgentDataGateway, knowledge_db: Session):
        self.structured = structured
        self.knowledge_db = knowledge_db

    def __getattr__(self, name):
        return getattr(self.structured, name)

    def search_risk_knowledge(self, query: str, category: str | None = None, limit: int = 5) -> dict:
        return KnowledgeBaseService(self.knowledge_db).search(query, category, limit)


class RoadshowDemoService:
    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id

    def scenario(self) -> dict:
        engine, demo_db, customer, order, _, _ = self._snapshot()
        try:
            history = self._history(demo_db, customer.id, order.id)
            scores = (
                demo_db.query(CreditScoreHistory)
                .filter(CreditScoreHistory.customer_id == customer.id)
                .order_by(CreditScoreHistory.calculated_at)
                .all()
            )
            recent = history[-5:]
            average = mean(item.amount for item in history)
            return {
                "scenario_code": "roadshow_200k_order",
                "title": "长期小额合作客户突然提交 20 万元订单",
                "duration_minutes": 3,
                "customer": {
                    "id": customer.id,
                    "company_name": customer.company_name,
                    "country": customer.country,
                    "cooperation_days": (order.order_time.date() - customer.cooperation_start_date).days,
                    "identity_verified": customer.identity_verified,
                    "demo_marker": "IN_MEMORY_ROADSHOW_ONLY",
                },
                "historical_summary": {
                    "transaction_count": len(history),
                    "average_order_amount_usd": round(average, 2),
                    "recent_amounts_usd": [item.amount for item in recent],
                    "common_payment_method": "T/T 30/70",
                    "known_addresses": sorted({item.shipping_address for item in history}),
                },
                "incoming_order": {
                    "id": order.id,
                    "order_number": order.order_number,
                    "display_amount_cny": 200_000,
                    "system_amount_usd": order.amount,
                    "currency_note": "路演按约 7.2 汇率折算，系统比较口径为 USD",
                    "payment_method": order.payment_method,
                    "deposit_ratio": order.deposit_ratio,
                    "shipping_address": order.shipping_address,
                    "submitted_at": order.order_time,
                },
                "credit_trend": [
                    {
                        "score": score.total_score,
                        "risk_level": score.risk_level,
                        "calculated_at": score.calculated_at,
                        "version": score.rule_version,
                    }
                    for score in scores[-2:]
                ],
                "isolation_notice": (
                    "场景运行在一次性内存数据库；仅知识检索只读正式 knowledge_base，"
                    "真实客户、订单、评分、预警和会话均为零写入。"
                ),
            }
        finally:
            demo_db.close()
            engine.dispose()

    def analyze(self) -> dict:
        engine, demo_db, _, _, analysis, event = self._snapshot()
        try:
            return {
                "analysis": analysis,
                "alert": {
                    "id": f"DEMO-{event.id}",
                    "title": event.title,
                    "risk_level": event.risk_level,
                    "risk_score": event.risk_score,
                    "status": "演示预警已生成",
                    "demo_only": True,
                },
                "persisted_during_demo": False,
            }
        finally:
            demo_db.close()
            engine.dispose()

    def run_agent(self) -> dict:
        engine, demo_db, customer, _, _, _ = self._snapshot()
        try:
            gateway = _RoadshowGateway(
                SqlAlchemyAgentDataGateway(demo_db, self.merchant_id),
                self.db,
            )
            graph = AgentDecisionGraph(AgentToolRegistry(gateway))
            risk = graph.run("为什么风险这么高？请结合交易证据和风控知识说明。", customer.id)
            checklist = graph.run("生成调查清单，并参考外贸风控操作规范。", customer.id)
            return {
                "risk_explanation": self._execution(risk),
                "verification_checklist": self._execution(checklist),
                "conversation_persisted": False,
            }
        finally:
            demo_db.close()
            engine.dispose()

    def _snapshot(self):
        if not settings.roadshow_demo_enabled:
            raise LookupError("路演演示功能未启用")
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        demo_db = sessionmaker(bind=engine, expire_on_commit=False)()
        try:
            customer, order = self._seed_snapshot(demo_db)
            analysis = RiskAssessmentService(demo_db, self.merchant_id).analyze_order(
                customer,
                model_dict(order),
                order.id,
                persist_event=True,
            )
            demo_db.commit()
            event = demo_db.query(RiskEvent).filter(RiskEvent.order_id == order.id).one()
            return engine, demo_db, customer, order, analysis, event
        except Exception:
            demo_db.close()
            engine.dispose()
            raise

    def _seed_snapshot(self, db: Session) -> tuple[Customer, Transaction]:
        now = datetime.now(UTC).replace(tzinfo=None, second=0, microsecond=0)
        db.add(Merchant(id=self.merchant_id, name="路演内存商户", contact="demo-only"))
        for index, (code, name, thresholds, severity) in enumerate(RULE_CONFIGS, 1):
            db.add(RiskRuleConfig(
                id=index,
                rule_code=code,
                rule_name=name,
                threshold_config=thresholds,
                severity=severity,
                version="rules_v1",
            ))
        customer = Customer(
            id=ROADSHOW_CUSTOMER_ID,
            merchant_id=self.merchant_id,
            name="Daniel Ortiz",
            company_name="Orion Home Imports",
            country="Mexico",
            region="Latin America",
            registration_number="IN-MEMORY-DEMO-001",
            email="roadshow@example.com",
            phone="+86 138 0000 9999",
            industry="Home & Lifestyle Wholesale",
            main_product_category="家居用品",
            identity_verified=True,
            cooperation_start_date=date.today() - timedelta(days=760),
            notes="IN_MEMORY_ROADSHOW_ONLY",
        )
        db.add(customer)
        db.flush()

        historical_amounts = [2380, 2650, 2490, 2880, 2720, 3010, 2860, 3150]
        addresses = [
            "Central Warehouse, Mexico City",
            "Central Warehouse, Mexico City",
            "Central Warehouse, Mexico City",
            "Central Warehouse, Mexico City",
            "Central Warehouse, Mexico City",
            "Yiwu Procurement Hub A",
            "Central Warehouse, Mexico City",
            "Yiwu Procurement Hub A",
        ]
        for index, amount in enumerate(historical_amounts, 1):
            order_time = now - timedelta(days=(9 - index) * 8)
            db.add(Transaction(
                id=9000 + index,
                merchant_id=self.merchant_id,
                customer_id=customer.id,
                order_number=f"DEMO-ROADSHOW-{index:03d}",
                product_category="家居用品",
                product_name=f"长期小额补货订单 {index}",
                amount=amount,
                currency="USD",
                order_time=order_time,
                payment_time=order_time + timedelta(days=3),
                shipping_time=order_time + timedelta(days=5),
                delivery_time=order_time + timedelta(days=20),
                payment_method="T/T 30/70",
                deposit_ratio=0.3,
                final_payment_status="paid",
                refund_status="none",
                dispute_status="none",
                overdue_days=0,
                cancelled=False,
                shipping_country="Mexico",
                shipping_address=addresses[index - 1],
            ))
        db.flush()
        order = Transaction(
            id=ROADSHOW_ORDER_ID,
            merchant_id=self.merchant_id,
            customer_id=customer.id,
            order_number=ROADSHOW_ORDER_NUMBER,
            product_category="家居用品",
            product_name="20 万元家居用品集中采购单",
            amount=27_800,
            currency="USD",
            order_time=now,
            payment_time=None,
            shipping_time=None,
            delivery_time=None,
            payment_method="Open Account 90 days",
            deposit_ratio=0,
            final_payment_status="pending",
            refund_status="none",
            dispute_status="none",
            overdue_days=0,
            cancelled=False,
            shipping_country="Mexico",
            shipping_address="New Forwarder Warehouse, Guadalajara",
        )
        db.add(order)
        db.flush()
        common = {
            "merchant_id": self.merchant_id,
            "customer_id": customer.id,
            "dispute_score": 96,
            "identity_score": 94,
            "relationship_score": 78,
            "confidence_level": "高置信度",
        }
        db.add(CreditScoreHistory(
            id=1,
            **common,
            total_score=88,
            performance_score=96,
            stability_score=84,
            risk_level="较低风险",
            rule_version="demo_baseline_v1",
            calculated_at=now - timedelta(days=30),
        ))
        db.add(CreditScoreHistory(
            id=2,
            **common,
            total_score=68,
            performance_score=88,
            stability_score=42,
            risk_level="中等风险",
            rule_version="demo_current_v1",
            calculated_at=now,
        ))
        db.commit()
        return customer, order

    @staticmethod
    def _history(db: Session, customer_id: int, order_id: int) -> list[Transaction]:
        return (
            db.query(Transaction)
            .filter(Transaction.customer_id == customer_id, Transaction.id != order_id)
            .order_by(Transaction.order_time)
            .all()
        )

    @staticmethod
    def _execution(execution) -> dict:
        unique_evidence: dict[tuple[str, str], dict] = {}
        for result in execution.tool_results:
            for item in result.evidence:
                unique_evidence[(item.source_type, item.source_id)] = {
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "summary": item.summary,
                }
        return {
            "answer": execution.answer,
            "intent": execution.intent,
            "tools_used": list(dict.fromkeys(item.tool for item in execution.tool_results)),
            "evidence": list(unique_evidence.values()),
            "call_chain": execution.call_chain,
            "insufficient_data": execution.insufficient_data,
        }


__all__ = ["RoadshowDemoService"]
