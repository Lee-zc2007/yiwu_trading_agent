from typing import Any

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    customer_id: int | None = None
    conversation_id: str = Field(default="demo-conversation", max_length=120)


class ToolCallEvidence(BaseModel):
    tool: str
    arguments: dict[str, Any]
    summary: str


class AgentChatResponse(BaseModel):
    answer: str
    mode: str
    conversation_id: str
    tools_called: list[ToolCallEvidence]
    data_sources: list[str]
    related_customer_ids: list[int]
    related_order_ids: list[int]
    related_risk_event_ids: list[int]
    insufficient_data: bool = False
    disclaimer: str
