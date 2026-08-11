from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import agent_router, customers_router, demo_router, knowledge_router, risk_router, system_router, transactions_router
from .core.config import settings
from .core.database import Base, SessionLocal, engine, ensure_vector_index, initialize_vector_support
from .core.logging import configure_logging
from .data import seed_demo_data, seed_knowledge_base


configure_logging()
logger = getLogger("tradeguard")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_vector_support()
    Base.metadata.create_all(bind=engine)
    ensure_vector_index()
    with SessionLocal() as db:
        seed_demo_data(db)
        seed_knowledge_base(db)
    logger.info("TradeGuard AI initialized")
    yield


app = FastAPI(
    title="TradeGuard AI 外贸风控智能体",
    version=settings.app_version,
    description="面向义乌外贸商户的可复现信用评分、规则风控、异常检测和证据型 AI Agent。",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

for router in [system_router, customers_router, transactions_router, risk_router, knowledge_router, agent_router, demo_router]:
    app.include_router(router)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "data": None, "message": str(exc.detail)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"success": False, "data": None, "message": "服务器内部错误，请查看后端日志"})
