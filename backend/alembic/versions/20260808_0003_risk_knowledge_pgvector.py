"""add risk knowledge base with pgvector

Revision ID: 20260808_0003
Revises: 20260808_0002
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR


revision = "20260808_0003"
down_revision = "20260808_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == "postgresql"
    if is_postgresql:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    tables = set(sa.inspect(bind).get_table_names())
    if "knowledge_base" not in tables:
        embedding_type = VECTOR(384) if is_postgresql else sa.JSON()
        op.create_table(
            "knowledge_base",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=240), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("embedding", embedding_type, nullable=False),
            sa.Column("category", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_knowledge_base_title", "knowledge_base", ["title"])
        op.create_index("ix_knowledge_base_category", "knowledge_base", ["category"])
        op.create_index("ix_knowledge_base_created_at", "knowledge_base", ["created_at"])

    if is_postgresql:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_base_embedding_hnsw "
            "ON knowledge_base USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "knowledge_base" in tables:
        if bind.dialect.name == "postgresql":
            op.execute("DROP INDEX IF EXISTS ix_knowledge_base_embedding_hnsw")
        op.drop_table("knowledge_base")
