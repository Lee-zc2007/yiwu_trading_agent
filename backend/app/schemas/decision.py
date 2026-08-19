from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MitigationInput(BaseModel):
    mitigation_type: Literal[
        "DEPOSIT", "INSURANCE", "GUARANTEE", "LETTER_OF_CREDIT",
        "PLATFORM_PROTECTION", "PARTIAL_SHIPMENT", "ESCROW", "OTHER",
    ]
    verified: bool = False
    coverage_amount: float = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=12)
    valid_from: date | None = None
    valid_until: date | None = None
    description: str = Field(default="", max_length=2000)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()


class EvidenceInput(BaseModel):
    evidence_type: str = Field(min_length=2, max_length=60)
    status: Literal["pending", "collected", "verified", "rejected", "expired"] = "collected"
    verified: bool = False
    file_reference: str = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=3000)
    checksum: str = Field(default="", max_length=128)
    collected_at: datetime | None = None
    verified_at: datetime | None = None

    @field_validator("evidence_type")
    @classmethod
    def uppercase_type(cls, value: str) -> str:
        return value.upper()


class TransactionTermsInput(BaseModel):
    credit_days: int | None = Field(default=None, ge=0, le=3650)
    payment_due_date: datetime | None = None
    deposit_ratio: float | None = Field(default=None, ge=0, le=1)
    deposit_amount: float | None = Field(default=None, ge=0)
    final_payment_ratio: float | None = Field(default=None, ge=0, le=1)
    final_payment_due_type: str | None = Field(default=None, max_length=60)
    contract_signed: bool | None = None
    payer_matches_contract: bool | None = None
    payment_account_changed: bool | None = None
    payment_account_verified: bool | None = None
    planned_shipping_value: float | None = Field(default=None, ge=0)
    planned_payment_before_shipping: float | None = Field(default=None, ge=0)


class TransactionDecisionContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    amount: float | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=12)
    deposit_ratio: float | None = Field(default=None, ge=0, le=1)
    deposit_amount: float | None = Field(default=None, ge=0)
    confirmed_payment_amount: float | None = Field(default=None, ge=0)
    credit_days: int | None = Field(default=None, ge=0, le=3650)
    final_payment_ratio: float | None = Field(default=None, ge=0, le=1)
    final_payment_due_type: str | None = Field(default=None, max_length=60)
    contract_signed: bool | None = None
    identity_verified: bool | None = None
    payer_matches_contract: bool | None = None
    payment_account_changed: bool | None = None
    payment_account_verified: bool | None = None
    planned_shipping_value: float | None = Field(default=None, ge=0)
    planned_payment_before_shipping: float | None = Field(default=None, ge=0)
    shipped_value: float | None = Field(default=None, ge=0)
    delivered_value: float | None = Field(default=None, ge=0)
    product_category: str | None = Field(default=None, max_length=120)
    product_name: str | None = Field(default=None, max_length=200)
    payment_method: str | None = Field(default=None, max_length=80)
    shipping_country: str | None = Field(default=None, max_length=80)
    shipping_address: str | None = Field(default=None, max_length=300)
    payment_terms_verified: bool | None = None
    missing_fields: list[str] = Field(default_factory=list)
    evidence_items: list[EvidenceInput] = Field(default_factory=list)
    mitigations: list[MitigationInput] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def uppercase_context_currency(cls, value: str) -> str:
        return value.upper()


class DecisionEvaluateRequest(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    transaction_id: int | None = Field(default=None, gt=0)
    transaction_context: TransactionDecisionContext = Field(default_factory=TransactionDecisionContext)
    persist_snapshot: bool = False


class DecisionSimulateRequest(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    transaction_id: int | None = Field(default=None, gt=0)
    base_context: TransactionDecisionContext = Field(default_factory=TransactionDecisionContext)
    adjustments: dict[str, Any]


class TimelineEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event_type: str
    event_time: datetime
    amount: float | None
    currency: str
    description: str
    verified: bool
    created_at: datetime
