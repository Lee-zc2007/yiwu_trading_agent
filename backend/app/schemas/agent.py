"""AI Agent 对外 API Schema。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentChatRequest(BaseModel):
    """统一聊天请求；customer_id 同时兼容数字和前端空字符串。"""

    message: str = Field(min_length=1, max_length=2000)
    customer_id: int | None = None
    conversation_id: str = Field(default="", max_length=120)

    @field_validator("customer_id", mode="before")
    @classmethod
    def normalize_customer_id(cls, value):
        if value in (None, ""):
            return None
        return int(value)


class AgentEvidence(BaseModel):
    source_type: str
    source_id: str
    summary: str


class RelatedCustomer(BaseModel):
    id: int
    company_name: str = ""
    country: str = ""


class ToolCallEvidence(BaseModel):
    """为已有前端保留的工具调用详情。"""

    tool: str
    arguments: dict[str, Any]
    summary: str


class AgentCallChainStep(BaseModel):
    """决策图中的一个已完成节点。"""

    step: int
    node: str
    status: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AgentStateSnapshot(BaseModel):
    """每个图节点执行后的可序列化 Agent State。"""

    node: str
    message: str
    customer_id: int | None
    intent: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    final_answer: str = ""


class AgentChatResponse(BaseModel):
    # 新统一响应字段。
    answer: str
    tools_used: list[str]
    evidence: list[AgentEvidence]
    related_customer: RelatedCustomer | None
    related_orders: list[int]
    risk_events: list[int]

    # 会话、运行模式与安全状态。
    conversation_id: str
    mode: str
    intent: str
    insufficient_data: bool = False
    disclaimer: str
    call_chain: list[AgentCallChainStep] = Field(default_factory=list)
    state_history: list[AgentStateSnapshot] = Field(default_factory=list)

    # 兼容当前前端的旧字段，后续可在前端迁移完成后再弃用。
    tools_called: list[ToolCallEvidence] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    related_customer_ids: list[int] = Field(default_factory=list)
    related_order_ids: list[int] = Field(default_factory=list)
    related_risk_event_ids: list[int] = Field(default_factory=list)


class ConversationCreateRequest(BaseModel):
    title: str = Field(default="新会话", max_length=120)
    customer_id: int | None = None


class ConversationMessage(BaseModel):
    id: int | None = None
    role: str
    content: str
    created_at: datetime
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    evidence: list[AgentEvidence] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    conversation_id: str
    merchant_id: int
    user_id: str = "demo-user"
    title: str
    customer_id: int | None
    created_at: datetime
    updated_at: datetime
    messages: list[ConversationMessage]


class ConversationSummary(BaseModel):
    conversation_id: str
    merchant_id: int
    user_id: str = "demo-user"
    title: str
    customer_id: int | None
    message_count: int
    created_at: datetime
    updated_at: datetime
