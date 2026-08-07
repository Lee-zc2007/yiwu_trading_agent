from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionBase(BaseModel):
    customer_id: int = Field(gt=0)
    order_number: str = Field(min_length=1, max_length=80)
    product_category: str = Field(min_length=1, max_length=120)
    product_name: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0, le=1_000_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=12)
    order_time: datetime
    payment_time: datetime | None = None
    shipping_time: datetime | None = None
    delivery_time: datetime | None = None
    payment_method: str = Field(min_length=1, max_length=80)
    deposit_ratio: float = Field(default=0.3, ge=0, le=1)
    final_payment_status: str = Field(default="paid", max_length=40)
    refund_status: str = Field(default="none", max_length=40)
    dispute_status: str = Field(default="none", max_length=40)
    overdue_days: int = Field(default=0, ge=0, le=3650)
    cancelled: bool = False
    shipping_country: str = Field(min_length=1, max_length=80)
    shipping_address: str = Field(min_length=1, max_length=300)

    @field_validator("currency")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("order_time", "payment_time", "shipping_time", "delivery_time")
    @classmethod
    def naive_utc_datetime(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=None) if value else value


class TransactionCreate(TransactionBase):
    run_risk_analysis: bool = True


class TransactionResponse(TransactionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    merchant_id: int
    created_at: datetime
    updated_at: datetime
