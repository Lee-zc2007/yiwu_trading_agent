from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import router
from .core.config import settings
from .core.database import Base, SessionLocal, engine
from .data.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    description="义乌AI国际贸易智能体社会实践路演原型 REST API。所有企业与交易数据均为虚构演示数据。",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}

