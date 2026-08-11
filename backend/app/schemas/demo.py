"""三分钟社会实践路演 API Schema。"""

from typing import Any

from pydantic import BaseModel, Field

from .agent import AgentEvidence
from .risk import OrderRiskResponse


class RoadshowScenarioResponse(BaseModel):
    scenario_code: str
    title: str
    duration_minutes: int
    customer: dict[str, Any]
    historical_summary: dict[str, Any]
    incoming_order: dict[str, Any]
    credit_trend: list[dict[str, Any]]
    isolation_notice: str


class RoadshowAnalyzeResponse(BaseModel):
    analysis: OrderRiskResponse
    alert: dict[str, Any]
    persisted_during_demo: bool = False


class RoadshowAgentExecution(BaseModel):
    answer: str
    intent: str
    tools_used: list[str]
    evidence: list[AgentEvidence] = Field(default_factory=list)
    call_chain: list[dict[str, Any]] = Field(default_factory=list)
    insufficient_data: bool


class RoadshowAgentResponse(BaseModel):
    risk_explanation: RoadshowAgentExecution
    verification_checklist: RoadshowAgentExecution
    conversation_persisted: bool = False
