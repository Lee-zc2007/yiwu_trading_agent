"""initial TradeGuard schema

Revision ID: 20260807_0001
Revises: None
"""
from alembic import op

from backend.app.core.database import Base
from backend.app.models import *  # noqa: F403


revision = "20260807_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
