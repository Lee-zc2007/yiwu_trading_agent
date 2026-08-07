from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    company_name: str = Field(min_length=1, max_length=200)
    country: str = Field(min_length=1, max_length=80)
    region: str = Field(default="", max_length=100)
    registration_number: str = Field(default="", max_length=120)
    email: str = Field(default="", max_length=180)
    phone: str = Field(default="", max_length=80)
    industry: str = Field(default="", max_length=120)
    main_product_category: str = Field(default="", max_length=120)
    identity_verified: bool = False
    blacklist_status: bool = False
    watchlist_status: bool = False
    cooperation_start_date: date | None = None
    notes: str = Field(default="", max_length=3000)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    country: str | None = Field(default=None, min_length=1, max_length=80)
    region: str | None = None
    registration_number: str | None = None
    email: str | None = None
    phone: str | None = None
    industry: str | None = None
    main_product_category: str | None = None
    identity_verified: bool | None = None
    blacklist_status: bool | None = None
    watchlist_status: bool | None = None
    cooperation_start_date: date | None = None
    notes: str | None = None


class CustomerResponse(CustomerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    merchant_id: int
    current_credit_score: float | None = None
    credit_risk_level: str | None = None
    transaction_count: int = 0
    created_at: datetime
    updated_at: datetime


class CreditScoreResponse(BaseModel):
    id: int
    customer_id: int
    total_score: float
    performance_score: float
    stability_score: float
    dispute_score: float
    identity_score: float
    relationship_score: float
    risk_level: str
    confidence_level: str
    rule_version: str
    calculated_at: datetime
    explanation: list[str] = []
