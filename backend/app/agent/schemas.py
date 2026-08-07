from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session


@dataclass
class ToolContext:
    db: Session
    merchant_id: int


@dataclass
class ToolResult:
    tool: str
    arguments: dict[str, Any]
    data: Any
    summary: str
    sources: list[str] = field(default_factory=list)
    customer_ids: list[int] = field(default_factory=list)
    order_ids: list[int] = field(default_factory=list)
    event_ids: list[int] = field(default_factory=list)
