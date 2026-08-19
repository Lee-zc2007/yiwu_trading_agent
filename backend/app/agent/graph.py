"""Agent 决策图与零依赖状态机实现。

接口按照 LangGraph 的 ``State -> Node -> State`` 思路设计，并提供 ``invoke`` 方法。
项目当前没有安装 LangGraph，因此使用同步确定性状态机；未来引入 LangGraph 后可直接
复用这里的节点、AgentState 和 Tool Registry，而不改变 API 或风控安全边界。
"""

from copy import deepcopy
from importlib.util import find_spec
from typing import Any, TypedDict

from .context import TransactionContextExtractor, merge_context, required_field_status
from .intent import IntentRecognizer
from .schemas import AgentExecution, DecisionContextStore, EvidenceRef, ToolResult
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
    conversation_id: str
    transaction_id: int | None
    context_version: int
    transaction_context: dict[str, Any]
    previous_transaction_context: dict[str, Any]
    context_patch: dict[str, Any]
    required_fields: list[str]
    missing_fields: list[str]
    information_completeness: float
    next_best_question: str
    decision_result: dict[str, Any] | None
    comparison: dict[str, Any] | None


class AgentDecisionGraph:
    """可替换为 LangGraph CompiledGraph 的确定性决策图。"""

    def __init__(
        self,
        tools: AgentToolRegistry,
        intent_recognizer: IntentRecognizer | None = None,
        context_store: DecisionContextStore | None = None,
        merchant_id: int = 1,
    ):
        self.tools = tools
        self.intent_recognizer = intent_recognizer or IntentRecognizer()
        self.context_store = context_store
        self.merchant_id = merchant_id
        self.context_extractor = TransactionContextExtractor()

    def invoke(self, state: AgentState | dict[str, Any]) -> AgentState:
        """执行完整图；方法签名与 LangGraph ``invoke`` 保持一致。"""

        current = self._normalize_state(state)
        self._checkpoint(current, START)
        current = self.load_context(current)
        current = self.intent_detection(current)
        current = self.extract_context_patch(current)
        current = self.merge_decision_context(current)
        current = self.resolve_customer(current)
        current = self.check_required_fields(current)
        if self._is_decision_intent(current["intent"]) and current["missing_fields"]:
            current = self.choose_next_best_question(current)
            current = self.save_context(current)
            current["final_answer"] = (
                f"我已记录当前交易条件，信息完整度为 {current['information_completeness']:.0%}。"
                f"为继续计算风险敞口和授信条件，请补充：{current['next_best_question']}"
            )
            self._checkpoint(current, "Response Generation", {"source": "next_best_question"})
            self._checkpoint(current, END)
            return current
        current = self.tool_selection(current)
        current = self.tool_execution(current)
        current = self.evidence_collection(current)
        current = self.response_generation(current)
        if self._is_decision_intent(current["intent"]):
            current = self.save_context(current)
        self._checkpoint(current, END)
        return current

    def run(self, message: str, customer_id: int | None, conversation_id: str = "") -> AgentExecution:
        """Agent Service 使用的便捷入口。"""

        state = self.invoke({"message": message, "customer_id": customer_id, "conversation_id": conversation_id})
        return AgentExecution(
            answer=state["final_answer"],
            tool_results=state["tool_results"],
            insufficient_data=not self._has_required_result(state),
            # 该路径由确定性状态机和只读 Tool 产生，不是模拟数据或 Mock 回答。
            mode="deterministic",
            intent=state["intent"],
            call_chain=state["call_chain"],
            state_history=state["state_history"],
            transaction_id=state["transaction_id"],
            context_version=state["context_version"],
            transaction_context=state["transaction_context"],
            required_fields=state["required_fields"],
            missing_fields=state["missing_fields"],
            information_completeness=state["information_completeness"],
            next_best_question=state["next_best_question"],
            decision_result=state["decision_result"],
            comparison=state["comparison"],
        )

    def load_context(self, state: AgentState) -> AgentState:
        stored = self.context_store.load(self.merchant_id, state["conversation_id"]) if self.context_store and state["conversation_id"] else {}
        if stored:
            state["customer_id"] = state["customer_id"] or stored.get("customer_id")
            state["transaction_id"] = stored.get("transaction_id")
            state["context_version"] = int(stored.get("context_version", 1))
            state["transaction_context"] = dict(stored.get("transaction_context") or {})
            state["required_fields"] = list(stored.get("required_fields") or [])
            state["missing_fields"] = list(stored.get("missing_fields") or [])
            state["information_completeness"] = float(stored.get("information_completeness") or 0)
            state["next_best_question"] = str(stored.get("next_best_question") or "")
        state["previous_transaction_context"] = deepcopy(state["transaction_context"])
        self._checkpoint(state, "Load Context", {"context_version": state["context_version"], "has_context": bool(state["transaction_context"])})
        return state

    def extract_context_patch(self, state: AgentState) -> AgentState:
        state["context_patch"] = self.context_extractor.extract(
            state["message"], state["transaction_context"], state["missing_fields"]
        )
        if state["context_patch"] and (
            state["intent"] == "unknown"
            or (state["previous_transaction_context"] and state["intent"] != "modify_transaction_terms")
        ):
            state["intent"] = "transaction_decision"
        self._checkpoint(state, "Context Extraction", {"extracted_fields": sorted(state["context_patch"])})
        return state

    def merge_decision_context(self, state: AgentState) -> AgentState:
        state["transaction_context"] = merge_context(state["transaction_context"], state["context_patch"])
        self._checkpoint(state, "Context Merge", {"patched_fields": sorted(state["context_patch"])})
        return state

    def resolve_customer(self, state: AgentState) -> AgentState:
        if self._is_decision_intent(state["intent"]) and state["customer_id"]:
            result = self.tools.execute("get_customer_profile", {"customer_id": state["customer_id"]})
            state["tool_results"].append(result)
            if result.success and state["transaction_context"].get("identity_verified") is None:
                state["transaction_context"]["identity_verified"] = result.data.get("identity_verified")
            self._checkpoint(state, "Resolve Customer", {"customer_id": state["customer_id"], "success": result.success})
        else:
            self._checkpoint(state, "Resolve Customer", {"customer_id": state["customer_id"], "skipped": True})
        return state

    def check_required_fields(self, state: AgentState) -> AgentState:
        if self._is_decision_intent(state["intent"]):
            required, missing, completeness, question = required_field_status(state["transaction_context"])
            state["required_fields"] = required
            state["missing_fields"] = missing
            state["information_completeness"] = completeness
            state["next_best_question"] = question
        self._checkpoint(state, "Required Fields", {"missing_fields": state["missing_fields"], "information_completeness": state["information_completeness"]})
        return state

    def choose_next_best_question(self, state: AgentState) -> AgentState:
        self._checkpoint(state, "Next Best Question", {"question": state["next_best_question"]})
        return state

    def save_context(self, state: AgentState) -> AgentState:
        if self.context_store and state["conversation_id"]:
            stored = self.context_store.save(
                self.merchant_id,
                state["conversation_id"],
                customer_id=state["customer_id"],
                transaction_id=state["transaction_id"],
                transaction_context=state["transaction_context"],
                required_fields=state["required_fields"],
                missing_fields=state["missing_fields"],
                information_completeness=state["information_completeness"],
                next_best_question=state["next_best_question"],
            )
            state["context_version"] = stored["context_version"]
        self._checkpoint(state, "Save Context", {"context_version": state["context_version"]})
        return state

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

        if intent == "transaction_decision":
            calls.append(self._call("evaluate_credit_terms", {
                "transaction_context": state["transaction_context"],
                "customer_id": customer_id,
                "transaction_id": state["transaction_id"],
            }, purpose="transaction_decision"))
        elif intent == "modify_transaction_terms":
            calls.append(self._call("simulate_transaction_adjustment", {
                "base_context": state["previous_transaction_context"],
                "adjustments": state["context_patch"],
                "customer_id": customer_id,
                "transaction_id": state["transaction_id"],
            }, purpose="decision_simulation"))
        elif intent == "risk_methodology":
            calls.append(self._call("get_risk_evaluation_criteria", {}, purpose="system_methodology"))
        elif intent == "customer_profile":
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
        if state["intent"] == "transaction_decision":
            state["decision_result"] = next(
                (item.data for item in state["tool_results"] if item.tool == "evaluate_credit_terms" and item.success),
                None,
            )
        elif state["intent"] == "modify_transaction_terms":
            simulation = next(
                (item.data for item in state["tool_results"] if item.tool == "simulate_transaction_adjustment" and item.success),
                None,
            )
            if simulation:
                state["decision_result"] = simulation.get("after")
                state["comparison"] = simulation.get("comparison")
        self._checkpoint(state, "Response Generation", {"answer_generated": bool(state["final_answer"])})
        return state

    def _answer_from_results(self, intent: str, results: list[ToolResult], evidence: list[EvidenceRef]) -> str:
        by_tool = {result.tool: result.data for result in results}

        if intent == "transaction_decision" and "evaluate_credit_terms" in by_tool:
            data = by_tool["evaluate_credit_terms"]
            trust = data["customer_trust"]
            risk = data["transaction_risk"]
            exposure = data["risk_exposure"]
            evidence_data = data["evidence"]
            recommendations = "；".join(data.get("recommendations", [])[:5]) or "按当前条件继续人工复核"
            answer = (
                f"根据系统确定性交易决策，客户历史可信度为 {trust['trust_level']}（{trust['confidence_level']} 置信度），"
                f"本次交易风险为 {risk['risk_level']}。预计最大风险敞口为 "
                f"{exposure['projected_max_exposure']:,.2f} {exposure['currency']}，证据完整度为 {evidence_data['completeness']:.0%}。"
                f"当前建议状态：{data['decision_status']}。建议：{recommendations}。最终决策需人工确认。"
            )
        elif intent == "modify_transaction_terms" and "simulate_transaction_adjustment" in by_tool:
            data = by_tool["simulate_transaction_adjustment"]
            before, after, comparison = data["before"], data["after"], data["comparison"]
            answer = (
                f"已完成纯模拟，没有修改正式交易。调整前预计最大敞口为 "
                f"{before['risk_exposure']['projected_max_exposure']:,.2f} {before['risk_exposure']['currency']}，"
                f"调整后为 {after['risk_exposure']['projected_max_exposure']:,.2f} {after['risk_exposure']['currency']}，"
                f"变化 {comparison['projected_exposure_change']:,.2f}。建议状态从 "
                f"{comparison['decision_status_before']} 变为 {comparison['decision_status_after']}。"
            )
        elif intent == "risk_methodology" and "get_risk_evaluation_criteria" in by_tool:
            data = by_tool["get_risk_evaluation_criteria"]
            trust = data["customer_trust"]
            risk = data["transaction_risk"]
            exposure = data["risk_exposure"]
            evidence_data = data["evidence_completeness"]
            rules = "\n".join(
                f"| `{item['rule_code']}` | {item['rule_name']} | {item['severity']} |"
                for item in risk["enabled_rules"]
            )
            answer = (
                "## 系统对客户与交易风险的评价标准\n\n"
                f"当前采用 `{data['decision_version']}` 决策链和 `{risk['version']}` 规则版本。"
                "系统不判断客户是不是骗子，而是分别评价客户历史可信度和本次交易条件。\n\n"
                "### 1. Customer Trust：客户过去是否可靠\n\n"
                + "、".join(trust["indicators"])
                + f"。{trust['unknown_data_policy']}。\n\n"
                "### 2. Transaction Risk：本次交易是否异常\n\n"
                f"当前数据库启用了 {risk['enabled_rule_count']} 条规则：\n\n"
                "| 规则代码 | 规则名称 | 严重度 |\n|---|---|---|\n"
                f"{rules}\n\n"
                "### 3. Risk Exposure：可能损失多少未收款货值\n\n"
                f"- 当前敞口：`{exposure['formulas']['current']}`\n"
                f"- 预计最大敞口：`{exposure['formulas']['projected']}`\n\n"
                "### 4. Evidence、Mitigation 与 Credit Terms\n\n"
                f"- 关键证据：{'、'.join(evidence_data['critical_types'])}\n"
                f"- 证据完整度：{evidence_data['formula']}\n"
                f"- 可抵扣保障：{'、'.join(data['risk_mitigation']['monetary_coverage_types'])}\n"
                "- 系统给出定金、账期、敞口和付款/发货条件建议，但最终必须人工决策。\n\n"
                "### 5. Isolation Forest\n\n"
                "仅作为行为异常辅助信号，不能单独产生 HIGH 或 CRITICAL，也不能用于认定欺诈。"
            )
        elif intent == "customer_profile" and "get_customer_profile" in by_tool:
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
            "conversation_id": str(state.get("conversation_id", "")),
            "transaction_id": state.get("transaction_id"),
            "context_version": int(state.get("context_version", 1)),
            "transaction_context": dict(state.get("transaction_context", {})),
            "previous_transaction_context": dict(state.get("previous_transaction_context", {})),
            "context_patch": dict(state.get("context_patch", {})),
            "required_fields": list(state.get("required_fields", [])),
            "missing_fields": list(state.get("missing_fields", [])),
            "information_completeness": float(state.get("information_completeness", 0)),
            "next_best_question": str(state.get("next_best_question", "")),
            "decision_result": state.get("decision_result"),
            "comparison": state.get("comparison"),
        }

    @staticmethod
    def _is_decision_intent(intent: str) -> bool:
        return intent in {"transaction_decision", "modify_transaction_terms"}

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
            "risk_methodology": ["get_risk_evaluation_criteria"],
            "transaction_decision": ["evaluate_credit_terms"],
            "modify_transaction_terms": ["simulate_transaction_adjustment"],
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
            "transaction_id": state["transaction_id"],
            "context_version": state["context_version"],
            "transaction_context": deepcopy(state["transaction_context"]),
            "required_fields": list(state["required_fields"]),
            "missing_fields": list(state["missing_fields"]),
            "information_completeness": state["information_completeness"],
            "next_best_question": state["next_best_question"],
            "decision_result": deepcopy(state["decision_result"]),
            "comparison": deepcopy(state["comparison"]),
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


def build_agent_graph(
    tools: AgentToolRegistry,
    intent_recognizer: IntentRecognizer | None = None,
    context_store: DecisionContextStore | None = None,
    merchant_id: int = 1,
) -> AgentDecisionGraph:
    """统一图构建入口；未来可在此切换为 LangGraph StateGraph。"""

    return AgentDecisionGraph(tools, intent_recognizer, context_store, merchant_id)


def graph_status() -> dict[str, Any]:
    """报告当前图后端及 LangGraph 升级可用性。"""

    return {
        "enabled": True,
        "backend": "simple_state_machine",
        "langgraph_installed": find_spec("langgraph") is not None,
        "nodes": [START, "Load Context", "Intent Detection", "Context Extraction", "Context Merge", "Resolve Customer", "Required Fields", "Next Best Question", "Tool Selection", "Tool Execution", "Evidence Collection", "Response Generation", "Save Context", END],
    }


__all__ = ["AgentState", "AgentDecisionGraph", "build_agent_graph", "graph_status"]
