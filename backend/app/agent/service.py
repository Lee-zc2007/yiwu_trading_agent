from ..core.config import settings
from ..schemas.agent import AgentChatResponse
from .llm_agent import LLMAgent
from .mock_agent import MockAgent
from .schemas import ToolContext


class AgentService:
    def chat(self, context: ToolContext, message: str, customer_id: int | None, conversation_id: str) -> AgentChatResponse:
        runner = LLMAgent() if settings.agent_mode == "llm" else MockAgent()
        answer, calls, insufficient = runner.run(context, message, customer_id)
        return AgentChatResponse(
            answer=answer, mode=settings.agent_mode if settings.agent_mode == "llm" and settings.llm_api_key else "mock",
            conversation_id=conversation_id,
            tools_called=[{"tool": call.tool, "arguments": call.arguments, "summary": call.summary} for call in calls],
            data_sources=list(dict.fromkeys(source for call in calls for source in call.sources)),
            related_customer_ids=sorted(set(item for call in calls for item in call.customer_ids)),
            related_order_ids=sorted(set(item for call in calls for item in call.order_ids)),
            related_risk_event_ids=sorted(set(item for call in calls for item in call.event_ids)),
            insufficient_data=insufficient,
            disclaimer="Agent 仅基于工具返回的事实进行解释，不执行黑名单、暂停发货或最终交易决策。",
        )
