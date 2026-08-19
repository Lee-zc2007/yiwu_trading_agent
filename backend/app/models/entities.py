from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import VECTOR

from ..core.config import settings
from ..core.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    contact: Mapped[str] = mapped_column(String(160), default="")


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    company_name: Mapped[str] = mapped_column(String(200), index=True)
    country: Mapped[str] = mapped_column(String(80), index=True)
    region: Mapped[str] = mapped_column(String(100), default="")
    registration_number: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(180), default="")
    phone: Mapped[str] = mapped_column(String(80), default="")
    industry: Mapped[str] = mapped_column(String(120), default="")
    main_product_category: Mapped[str] = mapped_column(String(120), default="")
    identity_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    blacklist_status: Mapped[bool] = mapped_column(Boolean, default=False)
    watchlist_status: Mapped[bool] = mapped_column(Boolean, default=False)
    cooperation_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    profile_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="customer", cascade="all, delete-orphan")


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_number: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    product_category: Mapped[str] = mapped_column(String(120))
    product_name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(12), default="USD")
    order_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    payment_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    shipping_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivery_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payment_method: Mapped[str] = mapped_column(String(80))
    deposit_ratio: Mapped[float] = mapped_column(Float, default=0.3)
    final_payment_status: Mapped[str] = mapped_column(String(40), default="paid")
    refund_status: Mapped[str] = mapped_column(String(40), default="none")
    dispute_status: Mapped[str] = mapped_column(String(40), default="none")
    overdue_days: Mapped[int] = mapped_column(Integer, default=0)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    shipping_country: Mapped[str] = mapped_column(String(80))
    shipping_address: Mapped[str] = mapped_column(String(300))

    customer: Mapped[Customer] = relationship(back_populates="transactions")
    terms: Mapped["TransactionTerm | None"] = relationship(
        back_populates="transaction", cascade="all, delete-orphan", uselist=False
    )
    timeline_events: Mapped[list["TransactionTimelineEvent"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    evidence_items: Mapped[list["TransactionEvidenceItem"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )
    mitigations: Mapped[list["TransactionMitigation"]] = relationship(
        back_populates="transaction", cascade="all, delete-orphan"
    )


class TransactionTerm(Base, TimestampMixin):
    """交易合同与授信条款。

    ``transactions.deposit_ratio`` 暂时保留以兼容旧接口；新决策链优先读取本表，
    没有条款记录时再回退旧字段。这样可以渐进迁移而不破坏现有 MVP。
    """

    __tablename__ = "transaction_terms"
    __table_args__ = (UniqueConstraint("transaction_id", name="uq_transaction_terms_transaction"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    credit_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deposit_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    deposit_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_payment_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_payment_due_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    contract_signed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    payer_matches_contract: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    payment_account_changed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    payment_account_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    planned_shipping_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    planned_payment_before_shipping: Mapped[float | None] = mapped_column(Float, nullable=True)

    transaction: Mapped[Transaction] = relationship(back_populates="terms")


class TransactionTimelineEvent(Base):
    """付款、发货、交付、到期、延期、纠纷等可验证交易时间线。"""

    __tablename__ = "transaction_timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(12), default="USD")
    description: Mapped[str] = mapped_column(Text, default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    transaction: Mapped[Transaction] = relationship(back_populates="timeline_events")


class TransactionEvidenceItem(Base):
    """交易证据元数据；文件只保存受控引用和摘要，不保存敏感原文。"""

    __tablename__ = "transaction_evidence_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    evidence_type: Mapped[str] = mapped_column(String(60), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    file_reference: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    checksum: Mapped[str] = mapped_column(String(128), default="")
    collected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    transaction: Mapped[Transaction] = relationship(back_populates="evidence_items")


class TransactionMitigation(Base):
    """保险、担保、信用证等风险缓释；只有 verified 项可抵扣敞口。"""

    __tablename__ = "transaction_mitigations"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    mitigation_type: Mapped[str] = mapped_column(String(60), index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    coverage_amount: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(12), default="USD")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    transaction: Mapped[Transaction] = relationship(back_populates="mitigations")


class CreditScoreHistory(Base):
    __tablename__ = "credit_score_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    total_score: Mapped[float] = mapped_column(Float)
    performance_score: Mapped[float] = mapped_column(Float)
    stability_score: Mapped[float] = mapped_column(Float)
    dispute_score: Mapped[float] = mapped_column(Float)
    identity_score: Mapped[float] = mapped_column(Float)
    relationship_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(40))
    confidence_level: Mapped[str] = mapped_column(String(40))
    rule_version: Mapped[str] = mapped_column(String(40), default="credit_v1")
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class CustomerTrustSnapshot(Base):
    """Customer Trust v2 的确定性计算快照。"""

    __tablename__ = "customer_trust_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    transaction_count: Mapped[int] = mapped_column(Integer, default=0)
    cooperation_days: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    max_order_amount: Mapped[float] = mapped_column(Float, default=0)
    on_time_payment_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    overdue_count: Mapped[int] = mapped_column(Integer, default=0)
    average_overdue_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    refund_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    dispute_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    rejection_count: Mapped[int] = mapped_column(Integer, default=0)
    trust_level: Mapped[str] = mapped_column(String(40), default="developing", index=True)
    confidence_level: Mapped[str] = mapped_column(String(40), default="low")
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    calculation_version: Mapped[str] = mapped_column(String(40), default="customer_trust_v2")
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class RiskRuleConfig(Base):
    __tablename__ = "risk_rule_config"
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    rule_name: Mapped[str] = mapped_column(String(160))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    threshold_config: Mapped[dict] = mapped_column(JSON, default=dict)
    severity: Mapped[str] = mapped_column(String(30), default="medium")
    version: Mapped[str] = mapped_column(String(40), default="rules_v1")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class RiskEvent(Base, TimestampMixin):
    __tablename__ = "risk_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True, index=True)
    risk_type: Mapped[str] = mapped_column(String(80))
    risk_level: Mapped[str] = mapped_column(String(30), index=True)
    risk_score: Mapped[float] = mapped_column(Float)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    triggered_rules: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    assigned_to: Mapped[str] = mapped_column(String(120), default="")
    resolution: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    actor: Mapped[str] = mapped_column(String(120), default="demo-user")
    object_type: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    before_data: Mapped[dict] = mapped_column(JSON, default=dict)
    after_data: Mapped[dict] = mapped_column(JSON, default=dict)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AgentConversation(Base, TimestampMixin):
    """持久化 Agent 会话；对外使用字符串 conversation_id。"""

    __tablename__ = "agent_conversations"
    __table_args__ = (
        UniqueConstraint("merchant_id", "user_id", "conversation_id", name="uq_agent_conversation_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    conversation_id: Mapped[str] = mapped_column(String(120), index=True)
    # 以下两个字段用于兼容现有会话列表和恢复客户上下文；标题入库前必须脱敏。
    title: Mapped[str] = mapped_column(String(120), default="新会话")
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)

    messages: Mapped[list["AgentMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AgentMessage.created_at",
    )


class AgentMessage(Base):
    """会话消息；content 与 tool_calls 均只允许保存脱敏后的内容。"""

    __tablename__ = "agent_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), index=True)
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)

    conversation: Mapped[AgentConversation] = relationship(back_populates="messages")


class AgentDecisionContext(Base, TimestampMixin):
    """与聊天记录分离的结构化多轮交易决策上下文。"""

    __tablename__ = "agent_decision_contexts"
    __table_args__ = (
        UniqueConstraint("merchant_id", "user_id", "conversation_id", name="uq_agent_decision_context_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    conversation_id: Mapped[str] = mapped_column(String(120), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True, index=True)
    context_version: Mapped[int] = mapped_column(Integer, default=1)
    transaction_context: Mapped[dict] = mapped_column(JSON, default=dict)
    required_fields: Mapped[list] = mapped_column(JSON, default=list)
    missing_fields: Mapped[list] = mapped_column(JSON, default=list)
    information_completeness: Mapped[float] = mapped_column(Float, default=0)
    next_best_question: Mapped[str] = mapped_column(Text, default="")


class TransactionDecisionSnapshot(Base):
    """一次确定性交易决策的不可变快照，供审计和证据包复用。"""

    __tablename__ = "transaction_decision_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True, index=True)
    decision_status: Mapped[str] = mapped_column(String(60), index=True)
    decision_data: Mapped[dict] = mapped_column(JSON, default=dict)
    calculation_version: Mapped[str] = mapped_column(String(40), default="transaction_decision_v1")
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class TransactionEvidencePackage(Base):
    """交易证据包的结构化 JSON 与可选 HTML 快照。"""

    __tablename__ = "transaction_evidence_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    package_data: Mapped[dict] = mapped_column(JSON, default=dict)
    html_content: Mapped[str] = mapped_column(Text, default="")
    checksum: Mapped[str] = mapped_column(String(128), default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)


class KnowledgeBase(Base):
    """非结构化风控知识块。

    一行对应文本切分后的一个 chunk。交易、客户、评分和风险事件属于结构化业务
    数据，禁止写入本表。PostgreSQL 使用 VECTOR；SQLite 仅以 JSON 保存向量用于
    本地测试兼容。
    """

    __tablename__ = "knowledge_base"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(
        VECTOR(settings.embedding_dimensions).with_variant(JSON(), "sqlite")
    )
    category: Mapped[str] = mapped_column(String(80), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
