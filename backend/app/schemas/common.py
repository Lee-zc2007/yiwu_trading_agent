from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: str = "ok"


class Pagination(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class HealthData(BaseModel):
    status: str
    service: str
    version: str
    database: str
    redis: str
    agent_mode: str
    model_status: str
    timestamp: datetime


class SystemInfo(BaseModel):
    name: str
    version: str
    default_merchant_id: int
    features: list[str]
    disclaimer: str


class ImportErrorRow(BaseModel):
    row: int
    reason: str
    data: dict[str, Any] = Field(default_factory=dict)


class ImportResult(BaseModel):
    total_rows: int
    success_count: int
    failed_count: int
    errors: list[ImportErrorRow]
    recalculated_customers: list[int]
