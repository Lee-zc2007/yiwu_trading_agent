from datetime import UTC, datetime, timedelta
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models import CreditScoreHistory, Customer, RiskEvent, Transaction
from ...repositories.customers import CustomerRepository
from ...risk.service import RiskAssessmentService
from ...schemas.common import ApiResponse, Pagination
from ...schemas.risk import DashboardData, OrderRiskRequest, OrderRiskResponse, RiskEventResponse, RiskEventStatusUpdate
from ...services.audit import record_audit
from ..dependencies import get_merchant_id


router = APIRouter(prefix="/api/risk", tags=["风险"])

SCENARIOS = [
    {"code": "small_to_large", "title": "小额试单后突然大额采购", "description": "最近 5 笔小额订单后金额放大 8 倍", "customer_id": 1},
    {"code": "address_changes", "title": "短期频繁更换地址", "description": "30 天内出现多个收货地址", "customer_id": 6},
    {"code": "overdue_credit", "title": "连续逾期后要求赊账", "description": "连续异常履约并切换 Open Account", "customer_id": 10},
    {"code": "new_urgent", "title": "新客户要求紧急发货", "description": "低置信度新客户首笔大额采购", "customer_id": 2},
    {"code": "split_orders", "title": "频繁拆单规避审核", "description": "多笔订单金额接近 5 万美元阈值", "customer_id": 7},
    {"code": "payment_change", "title": "突然更换付款方式", "description": "从 T/T 切换为 90 天赊账", "customer_id": 12},
]


def event_data(event: RiskEvent) -> dict:
    return {column.name: getattr(event, column.name) for column in RiskEvent.__table__.columns}


@router.post("/analyze-order", response_model=ApiResponse[OrderRiskResponse])
def analyze_order(payload: OrderRiskRequest, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    customer = CustomerRepository(db, merchant_id).get(payload.customer_id)
    if not customer: raise HTTPException(404, "外商不存在或不属于当前商户")
    result = RiskAssessmentService(db, merchant_id).analyze_order(customer, payload.model_dump(exclude={"persist_event", "scenario_code"}), persist_event=payload.persist_event)
    db.commit()
    return {"data": result, "message": "风险检测完成；高风险操作仍需人工确认"}


@router.get("/alerts", response_model=ApiResponse[Pagination[RiskEventResponse]])
def list_alerts(
    risk_level: str = "", status: str = "", page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db),
):
    query = db.query(RiskEvent).filter(RiskEvent.merchant_id == merchant_id)
    if risk_level: query = query.filter(RiskEvent.risk_level == risk_level)
    if status: query = query.filter(RiskEvent.status == status)
    total = query.count(); rows = query.order_by(RiskEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"data": {"items": [event_data(item) for item in rows], "total": total, "page": page, "page_size": page_size, "pages": max(1, ceil(total / page_size))}}


@router.get("/alerts/{event_id}", response_model=ApiResponse[RiskEventResponse])
def get_alert(event_id: int, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    event = db.query(RiskEvent).filter(RiskEvent.id == event_id, RiskEvent.merchant_id == merchant_id).first()
    if not event: raise HTTPException(404, "风险事件不存在")
    return {"data": event_data(event)}


@router.put("/alerts/{event_id}/status", response_model=ApiResponse[RiskEventResponse])
def update_alert(event_id: int, payload: RiskEventStatusUpdate, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    event = db.query(RiskEvent).filter(RiskEvent.id == event_id, RiskEvent.merchant_id == merchant_id).first()
    if not event: raise HTTPException(404, "风险事件不存在")
    protected = {"pause_shipping", "blacklist"}
    if payload.action in protected and not payload.confirmed:
        raise HTTPException(400, "暂停发货或加入黑名单必须由用户明确确认")
    before = {"status": event.status, "resolution": event.resolution, "assigned_to": event.assigned_to}
    event.status, event.resolution, event.assigned_to = payload.status, payload.resolution, payload.assigned_to
    if payload.status in {"resolved", "closed", "false_positive"}: event.resolved_at = datetime.now(UTC).replace(tzinfo=None)
    customer = CustomerRepository(db, merchant_id).get(event.customer_id)
    if payload.action == "watchlist" and payload.confirmed: customer.watchlist_status = True
    if payload.action == "blacklist" and payload.confirmed: customer.blacklist_status = True
    record_audit(db, merchant_id, "risk_event", event.id, payload.action, before=before, after=payload.model_dump(), remark=payload.resolution)
    db.commit()
    return {"data": event_data(event), "message": "风险处置已记录到审计日志"}


@router.get("/dashboard", response_model=ApiResponse[DashboardData])
def risk_dashboard(merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    now = datetime.now(UTC).replace(tzinfo=None); today = now.replace(hour=0, minute=0, second=0, microsecond=0); month = today.replace(day=1)
    customers = db.query(Customer).filter(Customer.merchant_id == merchant_id).all()
    latest_scores = []
    for customer in customers:
        score = CustomerRepository(db, merchant_id).latest_score(customer.id)
        if score: latest_scores.append((customer, score))
    high_risk = [(customer, score) for customer, score in latest_scores if score.total_score < 60]
    unresolved = db.query(RiskEvent).filter(RiskEvent.merchant_id == merchant_id, RiskEvent.status.in_(["pending", "investigating"])).count()
    risk_order_amount = db.query(func.coalesce(func.sum(Transaction.amount), 0)).join(RiskEvent, RiskEvent.order_id == Transaction.id).filter(RiskEvent.merchant_id == merchant_id, RiskEvent.created_at >= month).scalar() or 0
    trend = []
    for days_ago in range(6, -1, -1):
        start = today - timedelta(days=days_ago); end = start + timedelta(days=1)
        trend.append({"date": start.strftime("%m-%d"), "alerts": db.query(RiskEvent).filter(RiskEvent.merchant_id == merchant_id, RiskEvent.created_at >= start, RiskEvent.created_at < end).count(), "high": db.query(RiskEvent).filter(RiskEvent.merchant_id == merchant_id, RiskEvent.created_at >= start, RiskEvent.created_at < end, RiskEvent.risk_level.in_(["high", "critical"])).count()})
    distribution = [{"name": level, "value": db.query(RiskEvent).filter(RiskEvent.merchant_id == merchant_id, RiskEvent.risk_level == level).count()} for level in ["low", "medium", "high", "critical"]]
    top = sorted(high_risk, key=lambda item: item[1].total_score)[:5]
    latest = db.query(RiskEvent).filter(RiskEvent.merchant_id == merchant_id).order_by(RiskEvent.created_at.desc()).limit(6).all()
    metrics = {"customer_count": len(customers), "today_orders": db.query(Transaction).filter(Transaction.merchant_id == merchant_id, Transaction.order_time >= today).count(), "high_risk_customers": len(high_risk), "unresolved_alerts": unresolved, "monthly_risk_amount": round(float(risk_order_amount), 2), "average_credit_score": round(sum(score.total_score for _, score in latest_scores) / max(1, len(latest_scores)), 2)}
    return {"data": {"metrics": metrics, "risk_trend": trend, "risk_distribution": distribution, "high_risk_customers": [{"id": customer.id, "company_name": customer.company_name, "country": customer.country, "score": score.total_score, "risk_level": score.risk_level} for customer, score in top], "latest_alerts": [{"id": event.id, "title": event.title, "risk_level": event.risk_level, "risk_score": event.risk_score, "status": event.status, "created_at": event.created_at.isoformat()} for event in latest]}}


@router.get("/demo-scenarios", response_model=ApiResponse[list[dict]])
def demo_scenarios():
    return {"data": SCENARIOS}


@router.post("/demo-scenarios/{code}/run", response_model=ApiResponse[OrderRiskResponse])
def run_demo_scenario(code: str, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    scenario = next((item for item in SCENARIOS if item["code"] == code), None)
    if not scenario: raise HTTPException(404, "演示场景不存在")
    customer = CustomerRepository(db, merchant_id).get(scenario["customer_id"])
    if not customer: raise HTTPException(404, "演示外商不存在，请重新初始化数据")
    history = db.query(Transaction).filter(Transaction.customer_id == customer.id).order_by(Transaction.order_time).all()
    average = sum(item.amount for item in history) / max(1, len(history))
    base = {"customer_id": customer.id, "amount": round(average * 1.1, 2), "product_category": customer.main_product_category, "product_name": "路演模拟订单", "payment_method": history[-1].payment_method if history else "T/T 30/70", "deposit_ratio": .3, "shipping_country": customer.country, "shipping_address": history[-1].shipping_address if history else f"Demo Address, {customer.country}", "order_time": datetime.now(UTC).replace(tzinfo=None)}
    if code == "small_to_large": base["amount"] = round(max(60000, average * 8), 2)
    elif code == "address_changes": base["shipping_address"] = "New Forwarder Warehouse, Rotterdam"
    elif code == "overdue_credit": base.update(amount=45000, payment_method="Open Account 90 days", deposit_ratio=0)
    elif code == "new_urgent": base.update(amount=85000, payment_method="Cash on Delivery", deposit_ratio=0)
    elif code == "split_orders": base["amount"] = 43800
    elif code == "payment_change": base.update(payment_method="Open Account 90 days", deposit_ratio=0)
    result = RiskAssessmentService(db, merchant_id).analyze_order(customer, {key: value for key, value in base.items() if key != "customer_id"}, persist_event=True)
    db.commit()
    return {"data": result, "message": f"已运行场景：{scenario['title']}"}
