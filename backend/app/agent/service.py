"""AI Agent Service 层。

统一执行链路：用户问题 -> 意图识别 -> 白名单工具 -> 业务证据 -> DeepSeek/确定性回答。
本服务不持有数据库 Session，也不会调用任何评分或风险计算函数。
"""

from ..core.config import settings
from ..schemas.agent import AgentChatResponse, AgentEvidence, RelatedCustomer
from .conversation import ConversationStore, conversation_manager
from .graph import build_agent_graph
from .intent import IntentRecognizer
from .llm_agent import LLMProvider, LLMAgent, OpenAICompatibleProvider
from .schemas import AgentDataGateway, DecisionContextStore, EvidenceRef, ToolResult
from .tools import AgentToolRegistry


DISCLAIMER = "Agent 仅基于工具返回的已有事实进行解释，不计算风险分，不执行黑名单、暂停发货或最终交易决策。"


class AgentService:
    """Agent 统一应用服务，可通过依赖注入替换数据网关和模型 Provider。"""

    def __init__(
        self,
        gateway: AgentDataGateway,
        merchant_id: int,
        conversations: ConversationStore | None = None,
        decision_contexts: DecisionContextStore | None = None,
        provider: LLMProvider | None = None,
    ):
        self.gateway = gateway
        self.merchant_id = merchant_id
        self.conversations = conversations or conversation_manager
        self.decision_contexts = decision_contexts
        self.intent_recognizer = IntentRecognizer()
        self.tools = AgentToolRegistry(gateway)
        self.graph = build_agent_graph(self.tools, self.intent_recognizer, decision_contexts, merchant_id)
        self.provider = provider

    def _runner(self):
        """构造 DeepSeek/OpenAI-compatible Runner，不提供 Mock 降级。"""

        if settings.agent_mode != "llm" or not settings.llm_api_key:
            return None
        provider = self.provider or OpenAICompatibleProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        return LLMAgent(self.tools, provider)

    @staticmethod
    def _collect_evidence(results: list[ToolResult]) -> list[AgentEvidence]:
        unique: dict[tuple[str, str], EvidenceRef] = {}
        for result in results:
            for item in result.evidence:
                unique[(item.source_type, item.source_id)] = item
        return [AgentEvidence(source_type=item.source_type, source_id=item.source_id, summary=item.summary) for item in unique.values()]

    @staticmethod
    def _related_customer(results: list[ToolResult], customer_ids: list[int]) -> RelatedCustomer | None:
        for result in results:
            if result.tool == "get_customer_profile" and isinstance(result.data, dict):
                return RelatedCustomer(id=result.data["customer_id"], company_name=result.data.get("company_name", ""), country=result.data.get("country", ""))
            if result.tool == "compare_customers" and result.success and result.data:
                compared = result.data.get("customers") or []
                if compared:
                    profile = compared[0]
                    return RelatedCustomer(id=profile["customer_id"], company_name=profile.get("company_name", ""), country=profile.get("country", ""))
        return RelatedCustomer(id=customer_ids[0]) if customer_ids else None

    def chat(self, message: str, customer_id: int | None, conversation_id: str = "") -> AgentChatResponse:
        conversation = self.conversations.ensure(self.merchant_id, conversation_id, customer_id, message)
        effective_customer_id = customer_id or conversation.customer_id or self.conversations.resolve_customer_id(
            self.merchant_id,
            conversation.conversation_id,
        )
        self.conversations.append_message(self.merchant_id, conversation.conversation_id, "user", message)

        # 交易授信计算始终由确定性状态机完成；其余意图在配置有效时优先由
        # DeepSeek 选择只读 Tool 并基于 Tool 证据组织回答。
        preliminary_intent = self.intent_recognizer.recognize(message, effective_customer_id)
        stored_context = self.decision_contexts.load(self.merchant_id, conversation.conversation_id) if self.decision_contexts else {}
        has_active_decision = bool(stored_context.get("transaction_context"))
        llm_enabled = settings.agent_mode == "llm" and bool(settings.llm_api_key)
        runner = self._runner() if llm_enabled else None
        if not llm_enabled:
            execution = self.graph.run(message, effective_customer_id, conversation.conversation_id)
        elif preliminary_intent.name in {"transaction_decision", "modify_transaction_terms"} or has_active_decision:
            # 风控计算先走确定性状态机，再由 DeepSeek 基于结果生成用户可见回答。
            deterministic_execution = self.graph.run(message, effective_customer_id, conversation.conversation_id)
            execution = runner.explain_deterministic_execution(
                message,
                effective_customer_id,
                deterministic_execution,
            )
        else:
            intent = preliminary_intent
            execution = runner.run(message, effective_customer_id, intent)
            execution.intent = execution.intent or intent.name
            if not execution.call_chain:
                execution.call_chain, execution.state_history = self.graph.trace_existing_execution(
                    message,
                    effective_customer_id,
                    execution.intent,
                    execution.tool_results,
                    execution.answer,
                )
        tools_used = list(dict.fromkeys(item.tool for item in execution.tool_results))
        evidence = self._collect_evidence(execution.tool_results)
        customer_ids = sorted({item for result in execution.tool_results for item in result.customer_ids})
        order_ids = sorted({item for result in execution.tool_results for item in result.order_ids})
        event_ids = sorted({item for result in execution.tool_results for item in result.event_ids})

        response = AgentChatResponse(
            answer=execution.answer,
            tools_used=tools_used,
            evidence=evidence,
            related_customer=self._related_customer(execution.tool_results, customer_ids),
            related_orders=order_ids,
            risk_events=event_ids,
            conversation_id=conversation.conversation_id,
            mode=execution.mode,
            intent=execution.intent,
            insufficient_data=execution.insufficient_data,
            disclaimer=DISCLAIMER,
            call_chain=execution.call_chain,
            state_history=execution.state_history,
            transaction_id=execution.transaction_id,
            context_version=execution.context_version,
            transaction_context=execution.transaction_context,
            required_fields=execution.required_fields,
            missing_fields=execution.missing_fields,
            information_completeness=execution.information_completeness,
            next_best_question=execution.next_best_question,
            decision_result=execution.decision_result,
            comparison=execution.comparison,
            # 以下字段继续服务现有前端，保持 MVP 无破坏升级。
            tools_called=[{"tool": item.tool, "arguments": item.arguments, "summary": item.summary} for item in execution.tool_results],
            data_sources=[f"{item.source_type}:{item.source_id}" for item in evidence],
            related_customer_ids=customer_ids,
            related_order_ids=order_ids,
            related_risk_event_ids=event_ids,
        )
        self.conversations.append_message(
            self.merchant_id,
            conversation.conversation_id,
            "assistant",
            response.answer,
            tools_used=response.tools_used,
            evidence=response.evidence,
            tool_calls=[
                {
                    "tool": item.tool,
                    "arguments": item.arguments,
                    "success": item.success,
                    "summary": item.summary,
                    "error_code": item.error_code,
                }
                for item in execution.tool_results
            ],
        )
        return response
