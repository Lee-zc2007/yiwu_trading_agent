from .agent import router as agent_router
from .customers import router as customers_router
from .demo import router as demo_router
from .knowledge import router as knowledge_router
from .risk import router as risk_router
from .system import router as system_router
from .transactions import router as transactions_router

__all__ = ["system_router", "customers_router", "transactions_router", "risk_router", "knowledge_router", "agent_router", "demo_router"]
