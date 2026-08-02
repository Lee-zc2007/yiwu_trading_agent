from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str
    service: str
    mode: str
    products: int
    date: str


class DashboardResponse(BaseModel):
    metrics: list[dict[str, Any]]
    inquiry_trend: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    countries: list[dict[str, Any]]
    funnel: list[dict[str, Any]]
    risks: list[dict[str, Any]]
    time_saving: list[dict[str, Any]]
    products: list[dict[str, Any]]
    order_status: list[dict[str, Any]]
    disclaimer: str


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: int
    name: str
    category: str
    sku: str
    image: str
    description: str
    price: float
    cost: float
    moq: int
    stock: int
    lead_days: int
    target_markets: str
    tags: str
    multilingual_points: str
    model_configuration: str = Field(alias="model_config", serialization_alias="model_config")
    popularity: int


class QuoteCalculationResponse(BaseModel):
    product_id: int
    quantity: int
    unit_price: float
    unit_cost: float
    discount: float
    packaging_fee: float
    freight: float
    insurance: float
    tax_rate: float
    incoterm: str
    inquiry_id: int | None = None
    subtotal: float
    tax: float
    total_cost: float
    total_amount: float
    expected_profit: float
    margin_rate: float
    margin_warning: bool
    valid_until: str
    delivery_date: str
    disclaimer: str


class RiskEvaluationResponse(BaseModel):
    score: int
    level: str
    factors: list[dict[str, Any]]
    top_reasons: list[str]
    recommendation: str
    payment_recommendation: str
    recommended_deposit_percent: int
    continue_trade: bool
    mitigations: list[str]
    disclaimer: str


class ContractAnalysisResponse(BaseModel):
    risk_level: str
    score: int
    issues: list[dict[str, Any]]
    safe_version: str
    disclaimer: str


class ProductGenerateRequest(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    target_country: str = Field(min_length=1, max_length=80)
    target_customer: str = Field(default="年轻家庭", max_length=120)
    style: str = Field(default="现代简约", max_length=80)
    color: str = Field(default="海盐蓝", max_length=80)
    price_range: str = Field(default="10-20 USD", max_length=80)
    usage: str = Field(default="日常使用", max_length=160)
    requirements: str = Field(default="环保、轻量", max_length=500)


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=60)
    sku: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=2000)
    price: float = Field(gt=0)
    cost: float = Field(ge=0)
    moq: int = Field(ge=1)
    stock: int = Field(ge=0)
    lead_days: int = Field(default=21, ge=1, le=365)
    target_markets: str = Field(default="全球")
    tags: str = Field(default="新品")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="zh", max_length=20)
    scenario: str | None = Field(default=None, max_length=40)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=30)


class InquiryCreateRequest(BaseModel):
    customer_id: int
    product_id: int
    quantity: int = Field(ge=1)
    target_price: float = Field(ge=0)
    payment_method: str = Field(default="T/T")
    destination: str = Field(min_length=1, max_length=120)
    expected_delivery: str = Field(default="30天内")


class QuoteCalculateRequest(BaseModel):
    product_id: int = 1
    quantity: int = Field(default=1000, ge=1, le=1_000_000)
    unit_price: float = Field(default=12.8, ge=0)
    unit_cost: float = Field(default=8.1, ge=0)
    discount: float = Field(default=3, ge=0, le=50)
    packaging_fee: float = Field(default=180, ge=0)
    freight: float = Field(default=980, ge=0)
    insurance: float = Field(default=60, ge=0)
    tax_rate: float = Field(default=2, ge=0, le=30)
    incoterm: str = Field(default="FOB", pattern="^(EXW|FOB|CIF)$")
    inquiry_id: int | None = None


class RiskEvaluateRequest(BaseModel):
    registered_years: int = Field(default=1, ge=0, le=100)
    profile_completeness: int = Field(default=60, ge=0, le=100)
    historical_orders: int = Field(default=0, ge=0)
    historical_amount: float = Field(default=0, ge=0)
    disputes: int = Field(default=0, ge=0)
    payment_method: str = Field(default="T/T")
    order_amount: float = Field(default=10_000, ge=0)
    address_complete: bool = True
    corporate_email: bool = True
    account_changes: int = Field(default=0, ge=0)
    verification_refused: bool = False
    urgent_language: bool = False
    behavior_consistent: bool = True


class ContractAnalyzeRequest(BaseModel):
    text: str = Field(min_length=10, max_length=50_000)


class LogisticsRequest(BaseModel):
    origin: str = Field(default="义乌")
    destination: str = Field(default="法国")
    weight_kg: float = Field(default=1200, gt=0, le=1_000_000)
    volume_cbm: float = Field(default=8, gt=0, le=100_000)
    desired_days: int = Field(default=25, ge=1, le=365)
    budget: float = Field(default=5000, ge=0)


class ImpactRequest(BaseModel):
    daily_inquiries: int = Field(default=24, ge=1, le=10_000)
    manual_reply_minutes: float = Field(default=15, ge=0)
    manual_quote_minutes: float = Field(default=20, ge=0)
    hourly_cost: float = Field(default=42, ge=0)
    fake_inquiry_rate: float = Field(default=18, ge=0, le=100)
    average_order_amount: float = Field(default=18_000, ge=0)
    conversion_rate: float = Field(default=8, ge=0, le=100)
    ai_automation_rate: float = Field(default=72, ge=0, le=100)


class StatusUpdateRequest(BaseModel):
    status: str = Field(min_length=1, max_length=40)


class ApiMessage(BaseModel):
    message: str
    data: dict[str, Any] | None = None
