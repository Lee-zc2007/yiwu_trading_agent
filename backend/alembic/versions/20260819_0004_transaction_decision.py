"""add transaction decision domain models

Revision ID: 20260819_0004
Revises: 20260808_0003
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_0004"
down_revision = "20260808_0003"
branch_labels = None
depends_on = None


def _indexes(table: str, columns: list[str]) -> None:
    for column in columns:
        op.create_index(f"ix_{table}_{column}", table, [column])


def upgrade() -> None:
    # 初始迁移会按当前 metadata 建表，因此与历史增量迁移保持相同的幂等策略。
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "transaction_terms" not in tables:
        op.create_table(
            "transaction_terms",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("merchant_id", sa.Integer(), nullable=False),
            sa.Column("transaction_id", sa.Integer(), nullable=False),
            sa.Column("credit_days", sa.Integer(), nullable=True),
            sa.Column("payment_due_date", sa.DateTime(), nullable=True),
            sa.Column("deposit_ratio", sa.Float(), nullable=True),
            sa.Column("deposit_amount", sa.Float(), nullable=True),
            sa.Column("final_payment_ratio", sa.Float(), nullable=True),
            sa.Column("final_payment_due_type", sa.String(length=60), nullable=True),
            sa.Column("contract_signed", sa.Boolean(), nullable=True),
            sa.Column("payer_matches_contract", sa.Boolean(), nullable=True),
            sa.Column("payment_account_changed", sa.Boolean(), nullable=True),
            sa.Column("payment_account_verified", sa.Boolean(), nullable=True),
            sa.Column("planned_shipping_value", sa.Float(), nullable=True),
            sa.Column("planned_payment_before_shipping", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("transaction_id", name="uq_transaction_terms_transaction"),
        )
        _indexes("transaction_terms", ["merchant_id", "transaction_id"])

    if "transaction_timeline_events" not in tables:
        op.create_table(
            "transaction_timeline_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("merchant_id", sa.Integer(), nullable=False),
            sa.Column("transaction_id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=40), nullable=False),
            sa.Column("event_time", sa.DateTime(), nullable=False),
            sa.Column("amount", sa.Float(), nullable=True),
            sa.Column("currency", sa.String(length=12), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("verified", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        _indexes("transaction_timeline_events", ["merchant_id", "transaction_id", "event_type", "event_time"])

    if "transaction_evidence_items" not in tables:
        op.create_table(
            "transaction_evidence_items",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("merchant_id", sa.Integer(), nullable=False),
            sa.Column("transaction_id", sa.Integer(), nullable=False),
            sa.Column("evidence_type", sa.String(length=60), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("verified", sa.Boolean(), nullable=False),
            sa.Column("file_reference", sa.String(length=500), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("checksum", sa.String(length=128), nullable=False),
            sa.Column("collected_at", sa.DateTime(), nullable=True),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        _indexes("transaction_evidence_items", ["merchant_id", "transaction_id", "evidence_type", "status"])

    if "transaction_mitigations" not in tables:
        op.create_table(
            "transaction_mitigations",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("merchant_id", sa.Integer(), nullable=False),
            sa.Column("transaction_id", sa.Integer(), nullable=False),
            sa.Column("mitigation_type", sa.String(length=60), nullable=False),
            sa.Column("verified", sa.Boolean(), nullable=False),
            sa.Column("coverage_amount", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(length=12), nullable=False),
            sa.Column("valid_from", sa.Date(), nullable=True),
            sa.Column("valid_until", sa.Date(), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        _indexes("transaction_mitigations", ["merchant_id", "transaction_id", "mitigation_type"])

    if "customer_trust_snapshots" not in tables:
        op.create_table(
            "customer_trust_snapshots",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("merchant_id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.Integer(), nullable=False),
            sa.Column("transaction_count", sa.Integer(), nullable=False),
            sa.Column("cooperation_days", sa.Integer(), nullable=False),
            sa.Column("total_amount", sa.Float(), nullable=False),
            sa.Column("max_order_amount", sa.Float(), nullable=False),
            sa.Column("on_time_payment_rate", sa.Float(), nullable=True),
            sa.Column("overdue_count", sa.Integer(), nullable=False),
            sa.Column("average_overdue_days", sa.Float(), nullable=True),
            sa.Column("refund_rate", sa.Float(), nullable=True),
            sa.Column("dispute_rate", sa.Float(), nullable=True),
            sa.Column("rejection_count", sa.Integer(), nullable=False),
            sa.Column("trust_level", sa.String(length=40), nullable=False),
            sa.Column("confidence_level", sa.String(length=40), nullable=False),
            sa.Column("missing_fields", sa.JSON(), nullable=False),
            sa.Column("calculation_version", sa.String(length=40), nullable=False),
            sa.Column("calculated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        _indexes("customer_trust_snapshots", ["merchant_id", "customer_id", "trust_level", "calculated_at"])

    if "agent_decision_contexts" not in tables:
        op.create_table(
            "agent_decision_contexts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("merchant_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.String(length=120), nullable=False),
            sa.Column("conversation_id", sa.String(length=120), nullable=False),
            sa.Column("customer_id", sa.Integer(), nullable=True),
            sa.Column("transaction_id", sa.Integer(), nullable=True),
            sa.Column("context_version", sa.Integer(), nullable=False),
            sa.Column("transaction_context", sa.JSON(), nullable=False),
            sa.Column("required_fields", sa.JSON(), nullable=False),
            sa.Column("missing_fields", sa.JSON(), nullable=False),
            sa.Column("information_completeness", sa.Float(), nullable=False),
            sa.Column("next_best_question", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("merchant_id", "user_id", "conversation_id", name="uq_agent_decision_context_scope"),
        )
        _indexes("agent_decision_contexts", ["merchant_id", "user_id", "conversation_id", "customer_id", "transaction_id"])

    if "transaction_decision_snapshots" not in tables:
        op.create_table(
            "transaction_decision_snapshots",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("merchant_id", sa.Integer(), nullable=False),
            sa.Column("customer_id", sa.Integer(), nullable=True),
            sa.Column("transaction_id", sa.Integer(), nullable=True),
            sa.Column("decision_status", sa.String(length=60), nullable=False),
            sa.Column("decision_data", sa.JSON(), nullable=False),
            sa.Column("calculation_version", sa.String(length=40), nullable=False),
            sa.Column("calculated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        _indexes("transaction_decision_snapshots", ["merchant_id", "customer_id", "transaction_id", "decision_status", "calculated_at"])

    if "transaction_evidence_packages" not in tables:
        op.create_table(
            "transaction_evidence_packages",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("merchant_id", sa.Integer(), nullable=False),
            sa.Column("transaction_id", sa.Integer(), nullable=False),
            sa.Column("package_data", sa.JSON(), nullable=False),
            sa.Column("html_content", sa.Text(), nullable=False),
            sa.Column("checksum", sa.String(length=128), nullable=False),
            sa.Column("generated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
            sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        _indexes("transaction_evidence_packages", ["merchant_id", "transaction_id", "generated_at"])


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table in [
        "transaction_evidence_packages",
        "transaction_decision_snapshots",
        "agent_decision_contexts",
        "customer_trust_snapshots",
        "transaction_mitigations",
        "transaction_evidence_items",
        "transaction_timeline_events",
        "transaction_terms",
    ]:
        if table in tables:
            op.drop_table(table)
