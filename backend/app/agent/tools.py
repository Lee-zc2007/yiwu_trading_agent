from sqlalchemy import or_

from ..models import Customer, RiskEvent, Transaction
from ..repositories.customers import CustomerRepository
from ..risk.scoring import CreditScoringService
from .schemas import ToolContext, ToolResult


def get_customer_profile(context: ToolContext, customer_id: int | None = None, query: str = "") -> ToolResult:
    customer = CustomerRepository(context.db, context.merchant_id).get(customer_id) if customer_id else context.db.query(Customer).filter(Customer.merchant_id == context.merchant_id, or_(Customer.company_name.ilike(f"%{query}%"), Customer.name.ilike(f"%{query}%"))).first()
    if not customer:
        return ToolResult("get_customer_profile", {"customer_id": customer_id, "query": query}, None, "未找到匹配外商")
    data = {column.name: getattr(customer, column.name) for column in Customer.__table__.columns}
    return ToolResult("get_customer_profile", {"customer_id": customer.id}, data, f"查询到 {customer.company_name} 的外商档案", [f"customers:{customer.id}"], [customer.id])


def get_customer_credit_score(context: ToolContext, customer_id: int) -> ToolResult:
    customer = CustomerRepository(context.db, context.merchant_id).get(customer_id)
    if not customer: return ToolResult("get_customer_credit_score", {"customer_id": customer_id}, None, "外商不存在")
    score, explanation = CreditScoringService(context.db, context.merchant_id).latest_or_calculate(customer)
    data = {column.name: getattr(score, column.name) for column in score.__table__.columns}; data["explanation"] = explanation
    return ToolResult("get_customer_credit_score", {"customer_id": customer_id}, data, f"当前信用分 {score.total_score:.1f}，{score.risk_level}，{score.confidence_level}", [f"credit_score_history:{score.id}"], [customer_id])


def get_customer_transactions(context: ToolContext, customer_id: int, limit: int = 10) -> ToolResult:
    rows = context.db.query(Transaction).filter(Transaction.merchant_id == context.merchant_id, Transaction.customer_id == customer_id).order_by(Transaction.order_time.desc()).limit(min(limit, 50)).all()
    data = [{column.name: getattr(item, column.name) for column in Transaction.__table__.columns} for item in rows]
    return ToolResult("get_customer_transactions", {"customer_id": customer_id, "limit": limit}, data, f"查询到最近 {len(rows)} 笔交易", [f"transactions:customer:{customer_id}"], [customer_id], [item.id for item in rows])


def get_order_risk_analysis(context: ToolContext, order_id: int) -> ToolResult:
    event = context.db.query(RiskEvent).filter(RiskEvent.merchant_id == context.merchant_id, RiskEvent.order_id == order_id).order_by(RiskEvent.created_at.desc()).first()
    if not event: return ToolResult("get_order_risk_analysis", {"order_id": order_id}, None, "该订单没有已保存的风险分析")
    data = {column.name: getattr(event, column.name) for column in RiskEvent.__table__.columns}
    return ToolResult("get_order_risk_analysis", {"order_id": order_id}, data, f"订单风险为 {event.risk_level}，得分 {event.risk_score:.1f}", [f"risk_events:{event.id}"], [event.customer_id], [order_id], [event.id])


def list_risk_alerts(context: ToolContext, customer_id: int | None = None, limit: int = 10) -> ToolResult:
    query = context.db.query(RiskEvent).filter(RiskEvent.merchant_id == context.merchant_id)
    if customer_id: query = query.filter(RiskEvent.customer_id == customer_id)
    rows = query.order_by(RiskEvent.risk_score.desc(), RiskEvent.created_at.desc()).limit(min(limit, 50)).all()
    data = [{column.name: getattr(item, column.name) for column in RiskEvent.__table__.columns} for item in rows]
    return ToolResult("list_risk_alerts", {"customer_id": customer_id, "limit": limit}, data, f"查询到 {len(rows)} 条风险预警", ["risk_events"], list({item.customer_id for item in rows}), [item.order_id for item in rows if item.order_id], [item.id for item in rows])


def compare_customers(context: ToolContext, customer_id_a: int, customer_id_b: int) -> ToolResult:
    results = []
    for customer_id in [customer_id_a, customer_id_b]:
        profile = get_customer_profile(context, customer_id); credit = get_customer_credit_score(context, customer_id); transactions = get_customer_transactions(context, customer_id, 50)
        if not profile.data: continue
        amounts = [item["amount"] for item in transactions.data]
        results.append({"profile": profile.data, "credit": credit.data, "transaction_summary": {"count": len(amounts), "total_amount": round(sum(amounts), 2), "average_amount": round(sum(amounts) / max(1, len(amounts)), 2)}})
    return ToolResult("compare_customers", {"customer_id_a": customer_id_a, "customer_id_b": customer_id_b}, results, f"完成 {len(results)} 个外商的事实对比", ["customers", "credit_score_history", "transactions"], [item for item in [customer_id_a, customer_id_b]])


def get_risk_event_detail(context: ToolContext, event_id: int) -> ToolResult:
    event = context.db.query(RiskEvent).filter(RiskEvent.id == event_id, RiskEvent.merchant_id == context.merchant_id).first()
    data = {column.name: getattr(event, column.name) for column in RiskEvent.__table__.columns} if event else None
    return ToolResult("get_risk_event_detail", {"event_id": event_id}, data, "已查询风险事件证据" if event else "风险事件不存在", [f"risk_events:{event_id}"] if event else [], [event.customer_id] if event else [], [event.order_id] if event and event.order_id else [], [event_id] if event else [])


def generate_verification_checklist(context: ToolContext, customer_id: int) -> ToolResult:
    customer = CustomerRepository(context.db, context.merchant_id).get(customer_id)
    if not customer: return ToolResult("generate_verification_checklist", {"customer_id": customer_id}, None, "外商不存在")
    alerts = list_risk_alerts(context, customer_id, 5)
    checklist = ["通过原登记邮箱或电话进行二次确认", "核验企业注册号与受益人信息", "确认付款账户主体与合同主体一致", "在发货前复核收货国家和最终地址"]
    codes = {rule.get("rule_code") for event in alerts.data for rule in event.get("triggered_rules", [])}
    if "PAYMENT_CHANGED" in codes: checklist.append("书面说明付款方式变更原因并验证新账户")
    if "AMOUNT_SURGE" in codes or "SMALL_TO_LARGE" in codes: checklist.append("提高定金比例并分阶段交付")
    return ToolResult("generate_verification_checklist", {"customer_id": customer_id}, checklist, f"基于档案和 {len(alerts.data)} 条预警生成核验清单", [f"customers:{customer_id}", "risk_events"], [customer_id], event_ids=alerts.event_ids)


TOOL_REGISTRY = {function.__name__: function for function in [get_customer_profile, get_customer_credit_score, get_customer_transactions, get_order_risk_analysis, list_risk_alerts, compare_customers, get_risk_event_detail, generate_verification_checklist]}
