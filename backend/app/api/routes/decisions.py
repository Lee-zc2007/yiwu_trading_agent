from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models import Transaction
from ...repositories.customers import CustomerRepository
from ...risk.decision import TransactionDecisionService
from ...schemas.common import ApiResponse
from ...schemas.decision import DecisionEvaluateRequest, DecisionSimulateRequest
from ..dependencies import get_merchant_id


router = APIRouter(prefix="/api/decisions", tags=["交易决策"])

ALLOWED_SIMULATION_FIELDS = {
    "deposit_ratio",
    "deposit_amount",
    "confirmed_payment_amount",
    "credit_days",
    "final_payment_ratio",
    "final_payment_due_type",
    "planned_shipping_value",
    "planned_payment_before_shipping",
    "contract_signed",
    "payer_matches_contract",
    "payment_account_changed",
    "payment_account_verified",
    "mitigations",
}


def _resolve_scope(db: Session, merchant_id: int, customer_id: int | None, transaction_id: int | None):
    transaction = None
    customer = None
    if transaction_id is not None:
        transaction = db.query(Transaction).filter(
            Transaction.id == transaction_id,
            Transaction.merchant_id == merchant_id,
        ).first()
        if transaction is None:
            raise HTTPException(404, "交易不存在或不属于当前商户")
        customer = transaction.customer
        if customer_id is not None and customer.id != customer_id:
            raise HTTPException(400, "customer_id 与 transaction_id 不匹配")
    elif customer_id is not None:
        customer = CustomerRepository(db, merchant_id).get(customer_id)
        if customer is None:
            raise HTTPException(404, "外商不存在或不属于当前商户")
    return customer, transaction


@router.post("/evaluate", response_model=ApiResponse[dict])
def evaluate_decision(
    payload: DecisionEvaluateRequest,
    merchant_id: int = Depends(get_merchant_id),
    db: Session = Depends(get_db),
):
    customer, transaction = _resolve_scope(db, merchant_id, payload.customer_id, payload.transaction_id)
    result = TransactionDecisionService(db, merchant_id).evaluate(
        transaction_context=payload.transaction_context.model_dump(exclude_none=True),
        customer=customer,
        transaction=transaction,
        persist_snapshot=payload.persist_snapshot,
    )
    if payload.persist_snapshot:
        db.commit()
    return {"data": result, "message": "交易授信与风险条件评估完成，最终决策需人工确认"}


@router.post("/simulate", response_model=ApiResponse[dict])
def simulate_decision(
    payload: DecisionSimulateRequest,
    merchant_id: int = Depends(get_merchant_id),
    db: Session = Depends(get_db),
):
    unsupported = sorted(set(payload.adjustments) - ALLOWED_SIMULATION_FIELDS)
    if unsupported:
        raise HTTPException(400, f"不支持模拟修改字段：{', '.join(unsupported)}")
    customer, transaction = _resolve_scope(db, merchant_id, payload.customer_id, payload.transaction_id)
    result = TransactionDecisionService(db, merchant_id).simulate(
        base_context=payload.base_context.model_dump(exclude_none=True),
        adjustments=payload.adjustments,
        customer=customer,
        transaction=transaction,
    )
    return {"data": result, "message": "模拟完成；未修改正式交易或条款"}
