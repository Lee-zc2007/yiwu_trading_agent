from datetime import UTC, datetime

from fastapi import APIRouter
from redis import Redis

from ml.model_registry import model_registry

from ...core.config import settings
from ...schemas.common import ApiResponse, HealthData, SystemInfo


router = APIRouter(tags=["系统"])


@router.get("/health", response_model=ApiResponse[HealthData])
def health():
    redis_status = "unavailable"
    try:
        client = Redis.from_url(settings.redis_url, socket_connect_timeout=.25)
        redis_status = "connected" if client.ping() else "unavailable"
    except Exception:
        redis_status = "optional-fallback"
    database = "postgresql" if settings.database_url.startswith("postgresql") else "sqlite-local-fallback"
    return {"data": {"status": "ok", "service": settings.app_name, "version": settings.app_version, "database": database, "redis": redis_status, "agent_mode": settings.agent_mode, "model_status": model_registry.status()["status"], "timestamp": datetime.now(UTC)}}


@router.get("/api/system/info", response_model=ApiResponse[SystemInfo])
def system_info():
    return {"data": {"name": "TradeGuard AI 外贸风控智能体", "version": settings.app_version, "default_merchant_id": settings.default_merchant_id, "features": ["外商档案", "交易管理", "信用评分", "12 条风险规则", "Isolation Forest", "风险预警闭环", "Mock/LLM Agent"], "disclaimer": "风险评分和模型结果仅供辅助判断，最终决策应由商户结合实际情况作出。"}}


@router.get("/api/system/model", response_model=ApiResponse[dict])
def model_status():
    """返回模型版本、训练样本量、特征清单和加载状态，不暴露模型文件。"""
    return {"data": model_registry.status()}
