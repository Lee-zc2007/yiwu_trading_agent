from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RuleResult(BaseModel):
    triggered: bool
    rule_code: str
    rule_name: str
    risk_level: str
    risk_score: float
    reason: str
    evidence: dict[str, Any]


class OrderRiskRequest(BaseModel):
    customer_id: int = Field(gt=0)
    amount: float = Field(gt=0)
    product_category: str = Field(min_length=1, max_length=120)
    product_name: str = Field(default="模拟新订单", min_length=1, max_length=200)
    payment_method: str = Field(min_length=1, max_length=80)
    deposit_ratio: float = Field(default=0.3, ge=0, le=1)
    shipping_country: str = Field(min_length=1, max_length=80)
    shipping_address: str = Field(min_length=1, max_length=300)
    order_time: datetime = Field(default_factory=datetime.now)
    persist_event: bool = True
    scenario_code: str | None = None

    @field_validator("order_time")
    @classmethod
    def naive_order_time(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=None)


class OrderRiskResponse(BaseModel):
    customer_id: int
    order_id: int | None
    risk_event_id: int | None
    credit_score: float
    credit_confidence: str
    overall_risk_score: float
    risk_level: Literal["low", "medium", "high", "critical"]
    statistical_anomaly_score: float
    anomaly_score: float
    triggered_rules: list[RuleResult]
    main_reasons: list[str]
    recommendations: list[str]
    model_version: str
    model_status: str
    rule_version: str
    disclaimer: str
    feature_snapshot: dict[str, float]


class RiskEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    merchant_id: int
    customer_id: int
    order_id: int | None
    risk_type: str
    risk_level: str
    risk_score: float
    title: str
    description: str
    triggered_rules: list
    evidence: dict
    status: str
    assigned_to: str
    resolution: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class RiskEventStatusUpdate(BaseModel):
    status: Literal["pending", "investigating", "confirmed", "false_positive", "resolved", "closed"]
    resolution: str = Field(default="", max_length=3000)
    assigned_to: str = Field(default="", max_length=120)
    action: Literal["review", "request_materials", "raise_deposit", "pause_shipping", "watchlist", "blacklist", "close"] = "review"
    confirmed: bool = False


class DashboardData(BaseModel):
    metrics: dict[str, float | int]
    risk_trend: list[dict[str, Any]]
    risk_distribution: list[dict[str, Any]]
    high_risk_customers: list[dict[str, Any]]
    latest_alerts: list[dict[str, Any]]
