from datetime import UTC, datetime
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models import CreditScoreHistory, Customer
from ...repositories.customers import CustomerRepository
from ...risk.scoring import CreditScoringService, CustomerTrustService
from ...schemas.common import ApiResponse, Pagination
from ...schemas.customer import CreditScoreResponse, CustomerCreate, CustomerResponse, CustomerUpdate
from ...services.audit import record_audit
from ..dependencies import get_merchant_id


router = APIRouter(prefix="/api/customers", tags=["外商"])


def customer_data(customer: Customer, repository: CustomerRepository) -> dict:
    score = repository.latest_score(customer.id)
    data = {column.name: getattr(customer, column.name) for column in Customer.__table__.columns}
    data.update(current_credit_score=score.total_score if score else None, credit_risk_level=score.risk_level if score else None, transaction_count=repository.transaction_count(customer.id))
    return data


@router.get("", response_model=ApiResponse[Pagination[CustomerResponse]])
def list_customers(
    search: str = "", country: str = "", credit_level: str = "", risk_level: str = "",
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db),
):
    repository = CustomerRepository(db, merchant_id)
    rows = [customer_data(item, repository) for item in repository.list(search, country)]
    if credit_level:
        rows = [item for item in rows if item["credit_risk_level"] == credit_level]
    if risk_level:
        rows = [item for item in rows if ("高风险" if (item["current_credit_score"] or 100) < 60 else "非高风险") == risk_level]
    total = len(rows); start = (page - 1) * page_size
    return {"data": {"items": rows[start:start + page_size], "total": total, "page": page, "page_size": page_size, "pages": max(1, ceil(total / page_size))}}


@router.post("", response_model=ApiResponse[CustomerResponse], status_code=201)
def create_customer(payload: CustomerCreate, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    customer = Customer(merchant_id=merchant_id, **payload.model_dump())
    db.add(customer); db.flush()
    score, _ = CreditScoringService(db, merchant_id).calculate(customer)
    record_audit(db, merchant_id, "customer", customer.id, "create", after=payload.model_dump(mode="json"))
    db.commit()
    return {"data": customer_data(customer, CustomerRepository(db, merchant_id)), "message": "外商已创建并完成初始信用评分"}


@router.get("/{customer_id}", response_model=ApiResponse[CustomerResponse])
def get_customer(customer_id: int, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    repository = CustomerRepository(db, merchant_id); customer = repository.get(customer_id)
    if not customer: raise HTTPException(404, "外商不存在或不属于当前商户")
    return {"data": customer_data(customer, repository)}


@router.get("/{customer_id}/trust", response_model=ApiResponse[dict])
def get_customer_trust(customer_id: int, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    """返回 Customer Trust v2；读取时不写快照，也不重新计算 legacy 信用分。"""

    customer = CustomerRepository(db, merchant_id).get(customer_id)
    if not customer:
        raise HTTPException(404, "外商不存在或不属于当前商户")
    return {"data": CustomerTrustService(db, merchant_id).calculate(customer, save=False)}


@router.put("/{customer_id}", response_model=ApiResponse[CustomerResponse])
def update_customer(customer_id: int, payload: CustomerUpdate, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    repository = CustomerRepository(db, merchant_id); customer = repository.get(customer_id)
    if not customer: raise HTTPException(404, "外商不存在或不属于当前商户")
    before = {key: getattr(customer, key) for key in payload.model_dump(exclude_unset=True)}
    for key, value in payload.model_dump(exclude_unset=True).items(): setattr(customer, key, value)
    customer.profile_updated_at = datetime.now(UTC).replace(tzinfo=None)
    CreditScoringService(db, merchant_id).calculate(customer)
    record_audit(db, merchant_id, "customer", customer.id, "update", before=before, after=payload.model_dump(exclude_unset=True, mode="json"))
    db.commit()
    return {"data": customer_data(customer, repository), "message": "外商资料已更新，信用评分已重算"}


@router.delete("/{customer_id}", response_model=ApiResponse[dict])
def delete_customer(customer_id: int, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    repository = CustomerRepository(db, merchant_id); customer = repository.get(customer_id)
    if not customer: raise HTTPException(404, "外商不存在或不属于当前商户")
    if repository.transaction_count(customer_id): raise HTTPException(409, "该外商存在交易记录，为保护审计链不能直接删除")
    db.query(CreditScoreHistory).filter(CreditScoreHistory.customer_id == customer_id).delete()
    record_audit(db, merchant_id, "customer", customer.id, "delete", before={"company_name": customer.company_name})
    db.delete(customer); db.commit()
    return {"data": {"id": customer_id}, "message": "外商已删除"}


def score_response(score: CreditScoreHistory, explanation: list[str] | None = None) -> dict:
    data = {column.name: getattr(score, column.name) for column in CreditScoreHistory.__table__.columns}
    data["explanation"] = explanation or []
    return data


@router.get("/{customer_id}/credit-score", response_model=ApiResponse[CreditScoreResponse])
def get_credit_score(customer_id: int, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    repo = CustomerRepository(db, merchant_id); customer = repo.get(customer_id)
    if not customer: raise HTTPException(404, "外商不存在")
    score, explanation = CreditScoringService(db, merchant_id).latest_or_calculate(customer); db.commit()
    return {"data": score_response(score, explanation)}


@router.post("/{customer_id}/credit-score/recalculate", response_model=ApiResponse[CreditScoreResponse])
def recalculate_credit_score(customer_id: int, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    customer = CustomerRepository(db, merchant_id).get(customer_id)
    if not customer: raise HTTPException(404, "外商不存在")
    score, explanation = CreditScoringService(db, merchant_id).calculate(customer); db.commit()
    return {"data": score_response(score, explanation), "message": "信用评分已重算并保存历史"}


@router.get("/{customer_id}/credit-score/history", response_model=ApiResponse[list[CreditScoreResponse]])
def credit_score_history(customer_id: int, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    if not CustomerRepository(db, merchant_id).get(customer_id): raise HTTPException(404, "外商不存在")
    rows = db.query(CreditScoreHistory).filter(CreditScoreHistory.merchant_id == merchant_id, CreditScoreHistory.customer_id == customer_id).order_by(CreditScoreHistory.calculated_at).all()
    return {"data": [score_response(item) for item in rows]}
