from datetime import UTC, datetime, timedelta
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models import Customer, RiskEvent, Transaction, TransactionEvidenceItem, TransactionMitigation, TransactionTerm
from ...repositories.customers import CustomerRepository
from ...risk.service import RiskAssessmentService
from ...schemas.common import ApiResponse, Pagination
from ...schemas.risk import DashboardData, OrderRiskRequest, OrderRiskResponse, RiskEventResponse, RiskEventStatusUpdate
from ...services.audit import record_audit
from ..dependencies import get_merchant_id


router = APIRouter(prefix="/api/risk", tags=["风险"])

def event_data(event: RiskEvent) -> dict:
    return {column.name: getattr(event, column.name) for column in RiskEvent.__table__.columns}


@router.post("/analyze-order", response_model=ApiResponse[OrderRiskResponse])
def analyze_order(payload: OrderRiskRequest, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    customer = CustomerRepository(db, merchant_id).get(payload.customer_id)
    if not customer: raise HTTPException(404, "外商不存在或不属于当前商户")
    result = RiskAssessmentService(db, merchant_id).analyze_order(customer, payload.model_dump(exclude={"persist_event"}), persist_event=payload.persist_event)
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
    transactions = db.query(Transaction).filter(Transaction.merchant_id == merchant_id).all()
    terms_by_transaction = {
        item.transaction_id: item
        for item in db.query(TransactionTerm).filter(TransactionTerm.merchant_id == merchant_id).all()
    }
    verified_coverage: dict[int, float] = {}
    for item in db.query(TransactionMitigation).filter(
        TransactionMitigation.merchant_id == merchant_id,
        TransactionMitigation.verified.is_(True),
    ).all():
        if item.mitigation_type in {"INSURANCE", "GUARANTEE", "LETTER_OF_CREDIT", "PLATFORM_PROTECTION", "ESCROW"}:
            verified_coverage[item.transaction_id] = verified_coverage.get(item.transaction_id, 0) + item.coverage_amount
    exposures: dict[int, float] = {}
    for transaction in transactions:
        terms = terms_by_transaction.get(transaction.id)
        payment_before_shipping = terms.planned_payment_before_shipping if terms and terms.planned_payment_before_shipping is not None else transaction.amount * transaction.deposit_ratio
        planned_shipping = terms.planned_shipping_value if terms and terms.planned_shipping_value is not None else transaction.amount
        exposures[transaction.id] = max(0, planned_shipping - payment_before_shipping - min(planned_shipping, verified_coverage.get(transaction.id, 0)))
    high_risk_order_ids = {
        event.order_id for event in db.query(RiskEvent).filter(
            RiskEvent.merchant_id == merchant_id,
            RiskEvent.risk_level.in_(["high", "critical"]),
            RiskEvent.order_id.is_not(None),
        ).all()
    }
    evidence_transaction_ids = {
        row[0] for row in db.query(TransactionEvidenceItem.transaction_id).filter(
            TransactionEvidenceItem.merchant_id == merchant_id,
            TransactionEvidenceItem.verified.is_(True),
        ).distinct().all()
    }
    due_soon = now + timedelta(days=7)
    metrics = {
        "customer_count": len(customers),
        "today_orders": db.query(Transaction).filter(Transaction.merchant_id == merchant_id, Transaction.order_time >= today).count(),
        "unresolved_alerts": unresolved,
        "unsecured_exposure": round(sum(exposures.values()), 2),
        "high_risk_exposure": round(sum(exposures.get(order_id, 0) for order_id in high_risk_order_ids), 2),
        "pending_credit_orders": sum(1 for term in terms_by_transaction.values() if (term.credit_days or 0) > 0),
        "credit_order_amount": round(sum(tx.amount for tx in transactions if (terms_by_transaction.get(tx.id) and (terms_by_transaction[tx.id].credit_days or 0) > 0)), 2),
        "evidence_missing_orders": sum(1 for tx in transactions if tx.id not in evidence_transaction_ids),
        "payments_due_soon": sum(1 for term in terms_by_transaction.values() if term.payment_due_date and now <= term.payment_due_date <= due_soon),
        "terms_adjustment_orders": sum(1 for tx in transactions if (terms_by_transaction.get(tx.id) and ((terms_by_transaction[tx.id].credit_days or 0) > 30 or (terms_by_transaction[tx.id].deposit_ratio if terms_by_transaction[tx.id].deposit_ratio is not None else tx.deposit_ratio) < .3))),
        # 兼容旧前端和外部调用方，后续版本再弃用。
        "high_risk_customers": len(high_risk),
        "monthly_risk_amount": round(float(risk_order_amount), 2),
        "average_credit_score": round(sum(score.total_score for _, score in latest_scores) / max(1, len(latest_scores)), 2),
    }
    return {"data": {"metrics": metrics, "risk_trend": trend, "risk_distribution": distribution, "high_risk_customers": [{"id": customer.id, "company_name": customer.company_name, "country": customer.country, "score": score.total_score, "risk_level": score.risk_level} for customer, score in top], "latest_alerts": [{"id": event.id, "title": event.title, "risk_level": event.risk_level, "risk_score": event.risk_score, "status": event.status, "created_at": event.created_at.isoformat()} for event in latest]}}
