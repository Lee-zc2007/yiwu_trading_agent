from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(60))
    sku: Mapped[str] = mapped_column(String(60), unique=True)
    image: Mapped[str] = mapped_column(String(255), default="")
    description: Mapped[str] = mapped_column(Text)
    price: Mapped[float] = mapped_column(Float)
    cost: Mapped[float] = mapped_column(Float)
    moq: Mapped[int] = mapped_column(Integer)
    stock: Mapped[int] = mapped_column(Integer)
    lead_days: Mapped[int] = mapped_column(Integer)
    target_markets: Mapped[str] = mapped_column(String(255))
    tags: Mapped[str] = mapped_column(String(255))
    multilingual_points: Mapped[str] = mapped_column(Text)
    model_config: Mapped[str] = mapped_column(Text, default="{}")
    popularity: Mapped[int] = mapped_column(Integer, default=70)


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(160))
    contact: Mapped[str] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(80), default="")
    registered_years: Mapped[int] = mapped_column(Integer)
    historical_orders: Mapped[int] = mapped_column(Integer)
    historical_amount: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(80))
    intent_level: Mapped[str] = mapped_column(String(30))
    risk_level: Mapped[str] = mapped_column(String(30))
    credit_score: Mapped[int] = mapped_column(Integer)
    last_contact: Mapped[str] = mapped_column(String(40))
    tags: Mapped[str] = mapped_column(String(255))
    profile_completeness: Mapped[int] = mapped_column(Integer, default=80)
    disputes: Mapped[int] = mapped_column(Integer, default=0)
    verification_refused: Mapped[bool] = mapped_column(Boolean, default=False)


class Inquiry(Base, TimestampMixin):
    __tablename__ = "inquiries"
    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_no: Mapped[str] = mapped_column(String(60), unique=True)
    customer_id: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    target_price: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String(80))
    destination: Mapped[str] = mapped_column(String(120))
    expected_delivery: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40))
    intent_score: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[int] = mapped_column(Integer)
    ai_summary: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    urgent_language: Mapped[bool] = mapped_column(Boolean, default=False)
    account_changes: Mapped[int] = mapped_column(Integer, default=0)


class Quote(Base, TimestampMixin):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_no: Mapped[str] = mapped_column(String(60), unique=True)
    inquiry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    product_id: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Float)
    discount: Mapped[float] = mapped_column(Float)
    packaging_fee: Mapped[float] = mapped_column(Float)
    freight: Mapped[float] = mapped_column(Float)
    insurance: Mapped[float] = mapped_column(Float)
    tax: Mapped[float] = mapped_column(Float)
    total_cost: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    expected_profit: Mapped[float] = mapped_column(Float)
    margin_rate: Mapped[float] = mapped_column(Float)
    incoterm: Mapped[str] = mapped_column(String(20))
    valid_until: Mapped[str] = mapped_column(String(40))
    delivery_date: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="draft")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[str] = mapped_column(String(60), unique=True)
    customer_id: Mapped[int] = mapped_column(Integer)
    product_id: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Float)
    profit: Mapped[float] = mapped_column(Float)
    payment_status: Mapped[str] = mapped_column(String(40))
    production_status: Mapped[str] = mapped_column(String(40))
    logistics_status: Mapped[str] = mapped_column(String(40))
    risk_status: Mapped[str] = mapped_column(String(40))
    expected_delivery: Mapped[str] = mapped_column(String(40))
    progress: Mapped[int] = mapped_column(Integer)


class RiskAssessment(Base, TimestampMixin):
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(Integer)
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(30))
    factors: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)


class ContractReview(Base, TimestampMixin):
    __tablename__ = "contract_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(30))
    issues: Mapped[str] = mapped_column(Text)
    safe_version: Mapped[str] = mapped_column(Text)


class AfterSalesCase(Base, TimestampMixin):
    __tablename__ = "after_sales_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_no: Mapped[str] = mapped_column(String(60), unique=True)
    customer: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(60))
    satisfaction: Mapped[float] = mapped_column(Float)
    sentiment: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(40))
    repurchase_probability: Mapped[int] = mapped_column(Integer)
    suggested_contact: Mapped[str] = mapped_column(String(40))
    suggestion: Mapped[str] = mapped_column(Text)


class ResearchMetric(Base, TimestampMixin):
    __tablename__ = "research_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    label: Mapped[str] = mapped_column(String(160))
    value: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="placeholder")


class DemoScenario(Base, TimestampMixin):
    __tablename__ = "demo_scenarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(40))
    messages: Mapped[str] = mapped_column(Text)
    risk_hint: Mapped[str] = mapped_column(String(80))

