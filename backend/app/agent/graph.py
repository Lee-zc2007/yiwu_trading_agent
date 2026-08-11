"""Agent 决策图与零依赖状态机实现。

接口按照 LangGraph 的 ``State -> Node -> State`` 思路设计，并提供 ``invoke`` 方法。
项目当前没有安装 LangGraph，因此使用同步确定性状态机；未来引入 LangGraph 后可直接
复用这里的节点、AgentState 和 Tool Registry，而不改变 API 或风控安全边界。
"""

from copy import deepcopy
from importlib.util import find_spec
from typing import Any, TypedDict

from .intent import IntentRecognizer
from .schemas import AgentExecution, EvidenceRef, ToolResult
from .tools import AgentToolRegistry


START = "START"
END = "END"


class AgentState(TypedDict):
    """决策图在各节点之间传递的完整状态。"""

    message: str
    customer_id: int | None
    intent: str
    entity_ids: list[int]
    tool_calls: list[dict[str, Any]]
    tool_results: list[ToolResult]
    evidence: list[EvidenceRef]
    final_answer: str
    call_chain: list[dict[str, Any]]
    state_history: list[dict[str, Any]]


class AgentDecisionGraph:
    """可替换为 LangGraph CompiledGraph 的确定性决策图。"""

    def __init__(self, tools: AgentToolRegistry, intent_recognizer: IntentRecognizer | None = None):
        self.tools = tools
        self.intent_recognizer = intent_recognizer or IntentRecognizer()

    def invoke(self, state: AgentState | dict[str, Any]) -> AgentState:
        """执行完整图；方法签名与 LangGraph ``invoke`` 保持一致。"""

        current = self._normalize_state(state)
        self._checkpoint(current, START)
        current = self.intent_detection(current)
        current = self.tool_selection(current)
        current = self.tool_execution(current)
        current = self.evidence_collection(current)
        current = self.response_generation(current)
        self._checkpoint(current, END)
        return current

    def run(self, message: str, customer_id: int | None) -> AgentExecution:
        """Agent Service 使用的便捷入口。"""

        state = self.invoke({"message": message, "customer_id": customer_id})
        return AgentExecution(
            answer=state["final_answer"],
            tool_results=state["tool_results"],
            insufficient_data=not self._has_required_result(state),
            mode="mock",
            intent=state["intent"],
            call_chain=state["call_chain"],
            state_history=state["state_history"],
        )

    def trace_existing_execution(
        self,
        message: str,
        customer_id: int | None,
        intent: str,
        tool_results: list[ToolResult],
        final_answer: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """为 LLM 已完成的 Tool Calling 重建图轨迹，不重复执行 Tool。"""

        state = self._normalize_state({"message": message, "customer_id": customer_id})
        self._checkpoint(state, START)
        state["intent"] = intent
        self._checkpoint(state, "Intent Detection", {"source": "llm_route_context"})
        state["tool_calls"] = [self._call(item.tool, item.arguments, purpose="llm_selected") for item in tool_results]
        self._checkpoint(state, "Tool Selection", {"selected_tools": [item.tool for item in tool_results], "source": "llm"})
        for result in tool_results:
            state["tool_results"].append(result)
            self._checkpoint(
                state,
                "Tool Execution",
                {"tool": result.tool, "arguments": deepcopy(result.arguments), "success": result.success, "error_code": result.error_code},
            )
        unique: dict[tuple[str, str], EvidenceRef] = {}
        for result in tool_results:
            if result.success:
                for item in result.evidence:
                    unique[(item.source_type, item.source_id)] = item
        state["evidence"] = list(unique.values())
        self._checkpoint(state, "Evidence Collection", {"evidence_count": len(state["evidence"])})
        state["final_answer"] = final_answer
        self._checkpoint(state, "Response Generation", {"source": "llm", "answer_generated": bool(final_answer)})
        self._checkpoint(state, END)
        return state["call_chain"], state["state_history"]

    def intent_detection(self, state: AgentState) -> AgentState:
        """Intent Detection：理解问题并只输出允许的业务意图。"""

        result = self.intent_recognizer.recognize(state["message"], state["customer_id"])
        state["intent"] = result.name
        state["entity_ids"] = result.entity_ids
        self._checkpoint(state, "Intent Detection", {"confidence": result.confidence})
        return state

    def tool_selection(self, state: AgentState) -> AgentState:
        """根据意图生成白名单 Tool 调用计划，不执行任何业务逻辑。"""

        customer_id = state["customer_id"]
        entity_ids = state["entity_ids"]
        intent = state["intent"]
        calls: list[dict[str, Any]] = []

        if intent == "customer_profile":
            target = customer_id or self._first(entity_ids)
            if target:
                calls.append(self._call("get_customer_profile", {"customer_id": target}))
        elif intent == "credit_status":
            target = customer_id or self._first(entity_ids)
            if target:
                calls.append(self._call("get_customer_credit_score", {"customer_id": target}))
        elif intent == "risk_analysis":
            if customer_id:
                # 单独读取已经保存的信用评分，便于调用链明确展示；订单风险 Tool
                # 仍会复用同一已有评分，不在 Agent 内重新计算。
                calls.append(self._call("get_customer_credit_score", {"customer_id": customer_id}))
            order_id = self._first(entity_ids)
            if order_id:
                calls.append(self._call("get_order_risk_analysis", {"order_id": order_id}))
            elif customer_id:
                # 订单风险 Tool 需要 order_id。只能经交易 Tool 解析，图和 LLM 都不
                # 能绕过网关查询数据库。
                calls.append(self._call("get_customer_transactions", {"customer_id": customer_id, "limit": 1}, purpose="resolve_order"))
            # RAG 只提供通用案例和操作参考，不参与风险分计算，也不替代订单 Tool。
            calls.append(self._call("search_risk_knowledge", {"query": state["message"], "limit": 3}, purpose="knowledge_context"))
        elif intent == "compare_customers" and len(entity_ids) >= 2:
            calls.append(self._call("compare_customers", {"customer_id_a": entity_ids[0], "customer_id_b": entity_ids[1]}))
        elif intent == "verification_checklist":
            target = customer_id or self._first(entity_ids)
            if target:
                calls.append(self._call("generate_verification_checklist", {"customer_id": target}))
                calls.append(self._call(
                    "search_risk_knowledge",
                    {"query": f"{state['message']} 高风险订单人工复核操作规范", "limit": 3},
                    purpose="knowledge_context",
                ))
        elif intent == "knowledge_search":
            calls.append(self._call("search_risk_knowledge", {"query": state["message"], "limit": 5}))
        else:
            # 兼容 MVP 已有意图；核心 A-E 分支仍保持清晰独立。
            calls.extend(self._compatibility_calls(intent, customer_id, entity_ids, state["message"]))

        state["tool_calls"] = calls
        self._checkpoint(state, "Tool Selection", {"selected_tools": [item["name"] for item in calls]})
        return state

    def tool_execution(self, state: AgentState) -> AgentState:
        """逐个执行 Tool，并把每次调用的前后状态保存到历史。"""

        index = 0
        while index < len(state["tool_calls"]):
            call = state["tool_calls"][index]
            result = self.tools.execute(call["name"], call["arguments"])
            state["tool_results"].append(result)
            self._checkpoint(
                state,
                "Tool Execution",
                {"tool": call["name"], "arguments": deepcopy(call["arguments"]), "success": result.success, "error_code": result.error_code},
            )

            if call.get("purpose") == "resolve_order" and result.success:
                recent = result.data.get("recent_transactions", [])
                if recent:
                    order_id = recent[0]["order_id"]
                    state["tool_calls"].append(self._call("get_order_risk_analysis", {"order_id": order_id}, purpose="analyze_resolved_order"))
            index += 1
        return state

    def evidence_collection(self, state: AgentState) -> AgentState:
        """汇总成功 Tool 返回的可追溯证据并去重。"""

        unique: dict[tuple[str, str], EvidenceRef] = {}
        for result in state["tool_results"]:
            if not result.success:
                continue
            for item in result.evidence:
                unique[(item.source_type, item.source_id)] = item
        state["evidence"] = list(unique.values())
        self._checkpoint(state, "Evidence Collection", {"evidence_count": len(state["evidence"])})
        return state

    def response_generation(self, state: AgentState) -> AgentState:
        """只使用 Tool 结果生成回答；不存在成功结果时明确说明数据不足。"""

        successful = [result for result in state["tool_results"] if result.success]
        if not self._has_required_result(state):
            required = set(self._required_tools(state["intent"]))
            failed = next((item for item in state["tool_results"] if item.tool in required and not item.success), None)
            failed = failed or next((item for item in state["tool_results"] if not item.success), None)
            reason = failed.error_message if failed else "缺少可执行的客户或订单标识"
            state["final_answer"] = f"数据不足，无法基于系统证据回答。原因：{reason}。"
        else:
            state["final_answer"] = self._answer_from_results(state["intent"], successful, state["evidence"])
        self._checkpoint(state, "Response Generation", {"answer_generated": bool(state["final_answer"])})
        return state

    def _answer_from_results(self, intent: str, results: list[ToolResult], evidence: list[EvidenceRef]) -> str:
        by_tool = {result.tool: result.data for result in results}

        if intent == "customer_profile" and "get_customer_profile" in by_tool:
            data = by_tool["get_customer_profile"]
            answer = (
                f"根据系统外商档案，{data['company_name']} 位于 {data['country']}，行业为"
                f"{data['industry'] or '未填写'}，合作开始时间为 {data['cooperation_start_date'] or '未填写'}，"
                f"认证状态为{'已认证' if data['identity_verified'] else '未认证'}。"
            )
        elif intent == "credit_status" and "get_customer_credit_score" in by_tool:
            data = by_tool["get_customer_credit_score"]
            details = "、".join(data["reasons"][:5])
            answer = (
                f"根据系统已保存的信用评分，该客户总分为 {data['total_score']:.1f} 分，"
                f"风险等级为 {data['risk_level']}，置信度为 {data['confidence_level']}。"
                f"分项依据：{details}。"
            )
        elif intent == "risk_analysis" and "get_order_risk_analysis" in by_tool:
            data = by_tool["get_order_risk_analysis"]
            reasons = data.get("abnormal_reasons") or [item["reason"] for item in data.get("triggered_rules", [])]
            reason_text = "\n".join(f"{index}. {reason}" for index, reason in enumerate(reasons[:5], 1))
            recommendations = "；".join(data.get("recommendations", [])[:4]) or "继续人工复核"
            answer = (
                f"结构化业务事实（SQL 服务）：根据系统对订单 #{data['order_id']} 的分析，该客户风险等级为 {data['risk_level']}，"
                f"综合风险分为 {data['overall_risk_score']:.1f}；系统读取的已有信用评分为 "
                f"{data['credit_score']:.1f} 分（{data['credit_confidence']}）。\n"
                f"主要原因包括：\n{reason_text}\n建议措施：{recommendations}。"
            )
            answer += self._knowledge_reference(by_tool.get("search_risk_knowledge"))
        elif intent == "compare_customers" and "compare_customers" in by_tool:
            first, second = by_tool["compare_customers"]["customers"]
            answer = (
                f"根据系统已有数据，{first['company_name']} 的信用分为 {self._score(first['credit_score'])}、"
                f"历史预警 {first['risk_alert_count']} 条、交易 {first['transaction_count']} 笔；"
                f"{second['company_name']} 的信用分为 {self._score(second['credit_score'])}、"
                f"历史预警 {second['risk_alert_count']} 条、交易 {second['transaction_count']} 笔。"
                "以上为事实对比，不代表 Agent 作出最终交易决策。"
            )
        elif intent == "verification_checklist" and "generate_verification_checklist" in by_tool:
            data = by_tool["generate_verification_checklist"]
            items = "\n".join(f"{index}. {item['item']}（依据：{item['basis']}）" for index, item in enumerate(data["items"], 1))
            answer = (
                f"根据系统已有的 {data['based_on_alert_count']} 条风险预警，{data['company_name']} 的人工核验清单如下：\n"
                f"{items}"
            )
            answer += self._knowledge_reference(by_tool.get("search_risk_knowledge"))
        elif intent == "knowledge_search" and "search_risk_knowledge" in by_tool:
            knowledge = by_tool["search_risk_knowledge"]
            items = knowledge.get("items", [])
            if items:
                excerpts = "\n".join(
                    f"{index}. [{item['category']}] {item['title']}：{item['content']}"
                    for index, item in enumerate(items[:5], 1)
                )
                answer = (
                    f"非结构化知识（RAG）：通过 {knowledge['retrieval_method']} 检索到以下参考：\n{excerpts}\n"
                    "以上为通用案例或操作规范，不代表任何当前客户已经发生相同事实。"
                )
            else:
                answer = "非结构化知识（RAG）：知识库中没有召回足够相关的内容。"
        elif intent == "risk_explanation" and "get_customer_profile" in by_tool and "get_customer_credit_score" in by_tool:
            profile = by_tool["get_customer_profile"]
            credit = by_tool["get_customer_credit_score"]
            alerts = by_tool.get("list_risk_alerts", {}).get("items", [])
            reasons = [
                rule.get("reason", "")
                for event in alerts
                for rule in event.get("triggered_rules", [])
                if rule.get("reason")
            ]
            reason_text = "；".join(list(dict.fromkeys(reasons))[:4]) or "当前没有已保存的规则命中证据"
            answer = (
                f"结构化业务事实（SQL 服务）：{profile['company_name']} 已保存信用分为 {credit['total_score']:.1f} "
                f"（{credit['risk_level']}，{credit['confidence_level']}）。已有风险证据：{reason_text}。"
            )
            answer += self._knowledge_reference(by_tool.get("search_risk_knowledge"))
        else:
            # 兼容意图也必须引用 Tool 的结构化摘要，不允许用模型常识补全。
            answer = "根据系统工具返回的信息：" + "；".join(result.summary for result in results) + "。"

        citations = self._citation_text(evidence)
        return f"{answer}\n\n证据来源：{citations}" if citations else answer

    def _compatibility_calls(self, intent: str, customer_id: int | None, entity_ids: list[int], message: str) -> list[dict[str, Any]]:
        if intent == "transaction_history" and customer_id:
            return [self._call("get_customer_transactions", {"customer_id": customer_id, "limit": 10})]
        if intent == "recent_alerts":
            return [self._call("list_risk_alerts", {"limit": 5})]
        if intent == "risk_event_detail" and entity_ids:
            return [self._call("get_risk_event_detail", {"event_id": entity_ids[0]})]
        if intent == "risk_explanation" and customer_id:
            return [
                self._call("get_customer_profile", {"customer_id": customer_id}),
                self._call("get_customer_credit_score", {"customer_id": customer_id}),
                self._call("list_risk_alerts", {"customer_id": customer_id, "limit": 5}),
                self._call("search_risk_knowledge", {"query": message, "limit": 3}, purpose="knowledge_context"),
            ]
        return []

    @staticmethod
    def _normalize_state(state: AgentState | dict[str, Any]) -> AgentState:
        message = str(state.get("message", "")).strip()
        return {
            "message": message,
            "customer_id": state.get("customer_id"),
            "intent": str(state.get("intent", "")),
            "entity_ids": list(state.get("entity_ids", [])),
            "tool_calls": list(state.get("tool_calls", [])),
            "tool_results": list(state.get("tool_results", [])),
            "evidence": list(state.get("evidence", [])),
            "final_answer": str(state.get("final_answer", "")),
            "call_chain": list(state.get("call_chain", [])),
            "state_history": list(state.get("state_history", [])),
        }

    @staticmethod
    def _call(name: str, arguments: dict[str, Any], purpose: str = "business_query") -> dict[str, Any]:
        return {"name": name, "arguments": arguments, "purpose": purpose}

    @staticmethod
    def _first(values: list[int]) -> int | None:
        return values[0] if values else None

    @staticmethod
    def _score(value: float | None) -> str:
        return "暂无已保存评分" if value is None else f"{value:.1f} 分"

    @staticmethod
    def _required_tools(intent: str) -> list[str]:
        """定义每个意图真正完成所必需的目标 Tool。"""

        return {
            "customer_profile": ["get_customer_profile"],
            "credit_status": ["get_customer_credit_score"],
            "risk_analysis": ["get_order_risk_analysis"],
            "compare_customers": ["compare_customers"],
            "verification_checklist": ["generate_verification_checklist"],
            "transaction_history": ["get_customer_transactions"],
            "recent_alerts": ["list_risk_alerts"],
            "risk_event_detail": ["get_risk_event_detail"],
            "risk_explanation": ["get_customer_profile", "get_customer_credit_score"],
            "knowledge_search": ["search_risk_knowledge"],
        }.get(intent, [])

    def _has_required_result(self, state: AgentState) -> bool:
        required = self._required_tools(state["intent"])
        if not required:
            return False
        successful = {item.tool for item in state["tool_results"] if item.success}
        return all(name in successful for name in required)

    @staticmethod
    def _citation_text(evidence: list[EvidenceRef]) -> str:
        return "；".join(
            f"{item.summary}（{item.source_type} #{item.source_id}）"
            for item in evidence[:8]
        ) or "无可用证据"

    @staticmethod
    def _knowledge_reference(knowledge: dict[str, Any] | None) -> str:
        """将 RAG 结果标记为通用参考，避免与当前客户事实混淆。"""

        items = knowledge.get("items", []) if knowledge else []
        if not items:
            return ""
        references = "\n".join(
            f"- {item['title']}：{item['content']}"
            for item in items[:3]
        )
        return (
            "\n\n非结构化知识参考（RAG，不是当前客户事实）：\n"
            f"{references}"
        )

    def _checkpoint(self, state: AgentState, node: str, detail: dict[str, Any] | None = None) -> None:
        """保存节点调用链和完整可序列化 state 快照。"""

        state["call_chain"].append({
            "step": len(state["call_chain"]),
            "node": node,
            "status": "completed",
            "detail": detail or {},
        })
        state["state_history"].append({
            "node": node,
            "message": state["message"],
            "customer_id": state["customer_id"],
            "intent": state["intent"],
            "tool_calls": deepcopy(state["tool_calls"]),
            "tool_results": [self._serialize_tool_result(item) for item in state["tool_results"]],
            "evidence": [self._serialize_evidence(item) for item in state["evidence"]],
            "final_answer": state["final_answer"],
        })

    @staticmethod
    def _serialize_tool_result(result: ToolResult) -> dict[str, Any]:
        return {
            "tool": result.tool,
            "arguments": deepcopy(result.arguments),
            "success": result.success,
            "data": deepcopy(result.data),
            "summary": result.summary,
            "error_code": result.error_code,
            "error_message": result.error_message,
        }

    @staticmethod
    def _serialize_evidence(item: EvidenceRef) -> dict[str, str]:
        return {"source_type": item.source_type, "source_id": item.source_id, "summary": item.summary}


def build_agent_graph(tools: AgentToolRegistry, intent_recognizer: IntentRecognizer | None = None) -> AgentDecisionGraph:
    """统一图构建入口；未来可在此切换为 LangGraph StateGraph。"""

    return AgentDecisionGraph(tools, intent_recognizer)


def graph_status() -> dict[str, Any]:
    """报告当前图后端及 LangGraph 升级可用性。"""

    return {
        "enabled": True,
        "backend": "simple_state_machine",
        "langgraph_installed": find_spec("langgraph") is not None,
        "nodes": [START, "Intent Detection", "Tool Selection", "Tool Execution", "Evidence Collection", "Response Generation", END],
    }


__all__ = ["AgentState", "AgentDecisionGraph", "build_agent_graph", "graph_status"]
