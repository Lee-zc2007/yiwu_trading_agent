from fastapi import Header, HTTPException

from ..core.config import settings


def get_merchant_id(x_merchant_id: int | None = Header(default=None, alias="X-Merchant-ID")) -> int:
    merchant_id = x_merchant_id or settings.default_merchant_id
    if merchant_id <= 0:
        raise HTTPException(status_code=400, detail="无效商户 ID")
    return merchant_id


def get_user_id(x_user_id: str | None = Header(default=None, alias="X-User-ID")) -> str:
    """获取会话所属用户；当前演示环境默认使用非敏感别名。"""

    user_id = (x_user_id or "demo-user").strip()
    if not user_id or len(user_id) > 240:
        raise HTTPException(status_code=400, detail="无效用户 ID")
    return user_id
