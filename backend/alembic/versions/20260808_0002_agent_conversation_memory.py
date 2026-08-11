"""add persistent agent conversation memory

Revision ID: 20260808_0002
Revises: 20260807_0001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260808_0002"
down_revision = "20260807_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 初始迁移历史上使用当前 Base.metadata.create_all()。全新安装执行 0001 时可能
    # 已经包含本版本模型，因此这里必须幂等；从旧版 0001 升级时则正常创建缺失表。
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "agent_conversations" not in tables:
        op.create_table(
            "agent_conversations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("merchant_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(length=120), nullable=False),
            sa.Column("conversation_id", sa.String(length=120), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False, server_default="新会话"),
            sa.Column("customer_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("merchant_id", "user_id", "conversation_id", name="uq_agent_conversation_scope"),
        )
        op.create_index("ix_agent_conversations_merchant_id", "agent_conversations", ["merchant_id"])
        op.create_index("ix_agent_conversations_user_id", "agent_conversations", ["user_id"])
        op.create_index("ix_agent_conversations_conversation_id", "agent_conversations", ["conversation_id"])
        op.create_index("ix_agent_conversations_customer_id", "agent_conversations", ["customer_id"])

    if "agent_messages" not in tables:
        op.create_table(
            "agent_messages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=30), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("tool_calls", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])
        op.create_index("ix_agent_messages_role", "agent_messages", ["role"])
        op.create_index("ix_agent_messages_created_at", "agent_messages", ["created_at"])


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "agent_messages" in tables:
        op.drop_table("agent_messages")
    if "agent_conversations" in tables:
        op.drop_table("agent_conversations")
