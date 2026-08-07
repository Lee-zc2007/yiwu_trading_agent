from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
