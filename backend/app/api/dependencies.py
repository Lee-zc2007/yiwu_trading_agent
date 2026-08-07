from fastapi import Header, HTTPException

from ..core.config import settings


def get_merchant_id(x_merchant_id: int | None = Header(default=None, alias="X-Merchant-ID")) -> int:
    merchant_id = x_merchant_id or settings.default_merchant_id
    if merchant_id <= 0:
        raise HTTPException(status_code=400, detail="无效商户 ID")
    return merchant_id
