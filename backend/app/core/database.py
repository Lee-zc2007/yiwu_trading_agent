from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def initialize_vector_support() -> None:
    """在建表前启用 pgvector，并确保余弦检索使用 HNSW 索引。

    SQLite 是本地演示和自动化测试兼容模式，不执行任何 PostgreSQL 专属 SQL。
    """

    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def ensure_vector_index() -> None:
    """为知识块向量创建余弦距离 HNSW 索引；迁移与 create_all 两条路径均可用。"""

    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_base_embedding_hnsw "
            "ON knowledge_base USING hnsw (embedding vector_cosine_ops)"
        ))


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
