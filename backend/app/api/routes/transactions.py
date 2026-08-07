import io
from math import ceil
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.database import get_db
from ...models import Transaction
from ...repositories.customers import CustomerRepository
from ...risk.scoring import CreditScoringService
from ...risk.service import RiskAssessmentService
from ...schemas.common import ApiResponse, ImportResult, Pagination
from ...schemas.transaction import TransactionCreate, TransactionResponse
from ...services.audit import record_audit
from ..dependencies import get_merchant_id


router = APIRouter(prefix="/api/transactions", tags=["交易"])


def transaction_data(item: Transaction) -> dict:
    return {column.name: getattr(item, column.name) for column in Transaction.__table__.columns}


@router.get("", response_model=ApiResponse[Pagination[TransactionResponse]])
def list_transactions(
    customer_id: int | None = None, search: str = "", page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db),
):
    query = db.query(Transaction).filter(Transaction.merchant_id == merchant_id)
    if customer_id: query = query.filter(Transaction.customer_id == customer_id)
    if search: query = query.filter(Transaction.order_number.ilike(f"%{search}%"))
    total = query.count(); rows = query.order_by(Transaction.order_time.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"data": {"items": [transaction_data(item) for item in rows], "total": total, "page": page, "page_size": page_size, "pages": max(1, ceil(total / page_size))}}


@router.post("", response_model=ApiResponse[dict], status_code=201)
def create_transaction(payload: TransactionCreate, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    customer = CustomerRepository(db, merchant_id).get(payload.customer_id)
    if not customer: raise HTTPException(404, "外商不存在或不属于当前商户")
    values = payload.model_dump(exclude={"run_risk_analysis"})
    item = Transaction(merchant_id=merchant_id, **values)
    db.add(item)
    try: db.flush()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(409, "订单号已存在") from exc
    score, _ = CreditScoringService(db, merchant_id).calculate(customer)
    risk = RiskAssessmentService(db, merchant_id).analyze_order(customer, values, item.id, True) if payload.run_risk_analysis else None
    record_audit(db, merchant_id, "transaction", item.id, "create", after={"order_number": item.order_number, "amount": item.amount})
    db.commit()
    return {"data": {"transaction": transaction_data(item), "credit_score": score.total_score, "risk_analysis": risk}, "message": "交易已创建，信用评分与风险检测已更新"}


@router.get("/{transaction_id}", response_model=ApiResponse[TransactionResponse])
def get_transaction(transaction_id: int, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    item = db.query(Transaction).filter(Transaction.id == transaction_id, Transaction.merchant_id == merchant_id).first()
    if not item: raise HTTPException(404, "交易不存在")
    return {"data": transaction_data(item)}


@router.post("/import", response_model=ApiResponse[ImportResult])
async def import_transactions(file: UploadFile = File(...), merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".csv", ".xlsx"}: raise HTTPException(400, "仅支持 CSV 或 XLSX 文件")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(content) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(413, f"文件不能超过 {settings.max_upload_mb}MB")
    try:
        frame = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig") if suffix == ".csv" else pd.read_excel(io.BytesIO(content))
    except Exception as exc: raise HTTPException(400, f"文件解析失败：{exc}") from exc
    if len(frame) > 10_000: raise HTTPException(400, "单次最多导入 10000 行")
    required = {"customer_id", "order_number", "product_category", "product_name", "amount", "order_time", "payment_method", "shipping_country", "shipping_address"}
    missing = sorted(required - set(frame.columns))
    if missing: raise HTTPException(400, f"缺少必填字段：{', '.join(missing)}")

    errors, created, touched = [], [], set()
    defaults = {"currency": "USD", "deposit_ratio": .3, "final_payment_status": "paid", "refund_status": "none", "dispute_status": "none", "overdue_days": 0, "cancelled": False}
    for index, raw in frame.iterrows():
        data = {key: (None if pd.isna(value) else value) for key, value in raw.to_dict().items()}
        data = {**defaults, **{key: value for key, value in data.items() if value is not None}, "run_risk_analysis": False}
        try:
            payload = TransactionCreate.model_validate(data)
            customer = CustomerRepository(db, merchant_id).get(payload.customer_id)
            if not customer: raise ValueError("外商不存在或不属于当前商户")
            if db.query(Transaction).filter(Transaction.order_number == payload.order_number).first(): raise ValueError("订单号重复")
            item = Transaction(merchant_id=merchant_id, **payload.model_dump(exclude={"run_risk_analysis"}))
            db.add(item); db.flush(); created.append(item); touched.add(item.customer_id)
        except (ValidationError, ValueError, IntegrityError) as exc:
            db.rollback()
            reason = str(exc) if not isinstance(exc, ValidationError) else "; ".join(error["msg"] for error in exc.errors())
            errors.append({"row": int(index) + 2, "reason": reason, "data": {key: str(value)[:120] for key, value in data.items()}})
        else:
            db.commit()

    recalculated = []
    for customer_id in touched:
        customer = CustomerRepository(db, merchant_id).get(customer_id)
        CreditScoringService(db, merchant_id).calculate(customer); recalculated.append(customer_id)
        latest = db.query(Transaction).filter(Transaction.merchant_id == merchant_id, Transaction.customer_id == customer_id).order_by(Transaction.order_time.desc()).first()
        RiskAssessmentService(db, merchant_id).analyze_order(customer, transaction_data(latest), latest.id, True)
    record_audit(db, merchant_id, "transaction_import", file.filename or "upload", "import", after={"success": len(created), "failed": len(errors)})
    db.commit()
    return {"data": {"total_rows": len(frame), "success_count": len(created), "failed_count": len(errors), "errors": errors[:200], "recalculated_customers": recalculated}, "message": "导入完成，已自动重算信用评分并运行风险检测"}
