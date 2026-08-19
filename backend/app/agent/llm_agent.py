"""可扩展 LLM Provider 接口与 Tool Calling Agent。

当前提供 OpenAI-compatible 实现，可连接 GPT 及提供兼容接口的 Qwen 服务。未来
Claude、原生 Qwen 等适配器只需实现 ``LLMProvider.complete``，无需修改工具层或
Agent Service。
"""

import json
import time
from typing import Protocol

import httpx

from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schemas import AgentExecution, IntentResult, ToolResult
from .tools import AgentToolRegistry


class LLMProvider(Protocol):
    """GPT、Claude、Qwen 等模型适配器的最小接口。"""

    provider_name: str

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...


class OpenAICompatibleProvider:
    """OpenAI Chat Completions 兼容接口实现。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 60,
        max_retries: int = 2,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = max(5, float(timeout_seconds))
        self.max_retries = max(0, min(int(max_retries), 5))
        self.provider_name = "deepseek" if "deepseek" in self.base_url.lower() else "openai-compatible"

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload: dict = {"model": self.model, "messages": messages}
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
                    response.raise_for_status()
                    body = response.json()
                    return body["choices"][0]["message"]
                except httpx.HTTPStatusError as exc:
                    retryable = exc.response.status_code == 429 or exc.response.status_code >= 500
                    if not retryable or attempt >= self.max_retries:
                        raise
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt >= self.max_retries:
                        raise
                time.sleep(0.75 * (attempt + 1))
        raise RuntimeError("LLM provider 未返回结果")


class LLMAgent:
    """使用 DeepSeek 优先选择工具；失败时明确报错，不生成 Mock 回答。"""

    def __init__(self, tools: AgentToolRegistry, provider: LLMProvider):
        self.tools = tools
        self.provider = provider

    @staticmethod
    def _contains_internal_tool_markup(message: dict) -> bool:
        """识别兼容模型偶尔泄露到正文中的内部 Tool Calling 标记。"""

        content = str(message.get("content") or "")
        markers = (
            "<｜｜DSML｜｜tool_calls>",
            "<｜｜DSML｜｜invoke",
            "<|tool_calls|>",
            "<tool_call>",
        )
        return bool(message.get("tool_calls")) or any(marker in content for marker in markers)

    def _generate_final_answer(self, messages: list[dict]) -> str:
        """要求模型结束 Tool 阶段，并在标记泄露时做一次有限纠正。"""

        final_messages = [
            *messages,
            {
                "role": "system",
                "content": (
                    "受控 Tool 调用阶段已经结束。现在只根据上方 Tool 返回的证据生成最终中文回答。"
                    "不得再调用或请求任何 Tool，不得输出 XML、DSML、tool_calls 或 invoke 标记，也不得提及不存在的工具。"
                ),
            },
        ]
        final_message = self.provider.complete(final_messages)
        if self._contains_internal_tool_markup(final_message):
            final_messages.extend([
                {
                    "role": "assistant",
                    "content": str(final_message.get("content") or ""),
                },
                {
                    "role": "system",
                    "content": (
                        "上一条包含内部 Tool 标记，不能展示给用户。请重新输出最终答案："
                        "只使用已有 Tool 证据，输出普通 Markdown 中文，不再请求任何数据或工具。"
                    ),
                },
            ])
            final_message = self.provider.complete(final_messages)
        if self._contains_internal_tool_markup(final_message):
            raise ValueError("DeepSeek 最终回答包含内部 Tool 标记")
        answer = str(final_message.get("content") or "").strip()
        if not answer:
            raise ValueError("DeepSeek 最终回答为空")
        return answer

    def explain_deterministic_execution(
        self,
        message: str,
        customer_id: int | None,
        execution: AgentExecution,
    ) -> AgentExecution:
        """让 DeepSeek 基于确定性状态机结果生成最终回答。

        交易条件抽取、缺失字段判断、风险敞口和授信计算已经由状态机与 Tool
        完成。这里仅允许模型整理表达，确保每次用户可见回答都经过 DeepSeek，
        同时不把风险计算权交给模型。
        """

        evidence_payload = {
            "intent": execution.intent,
            "customer_id": customer_id,
            "deterministic_answer": execution.answer,
            "tool_results": [
                {
                    "tool": item.tool,
                    "success": item.success,
                    "data": item.data if item.success else None,
                    "error_code": item.error_code,
                    "error_message": item.error_message,
                }
                for item in execution.tool_results
            ],
            "transaction_id": execution.transaction_id,
            "transaction_context": execution.transaction_context,
            "required_fields": execution.required_fields,
            "missing_fields": execution.missing_fields,
            "information_completeness": execution.information_completeness,
            "next_best_question": execution.next_best_question,
            "decision_result": execution.decision_result,
            "comparison": execution.comparison,
        }
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_user_prompt(message, customer_id, execution.intent),
            },
            {
                "role": "system",
                "content": (
                    "以下 JSON 是确定性状态机和受控 Tool 已经完成的结果。你只负责生成最终中文回答，"
                    "不得重新计算、修改或补充任何风险分数、等级、敞口、定金比例或账期。"
                    "如果 missing_fields 非空，必须围绕 next_best_question 追问，不得假设缺失值；"
                    "如果存在 decision_result 或 comparison，必须准确引用其中的数字和结论。"
                    "不要声称你直接访问了数据库。\n"
                    + json.dumps(evidence_payload, ensure_ascii=False, default=str)
                ),
            },
        ]
        try:
            execution.answer = self._generate_final_answer(messages)
            execution.mode = f"llm:{self.provider.provider_name}"
            for step in execution.call_chain:
                if step.get("node") == "Response Generation":
                    step.setdefault("detail", {})["source"] = "deepseek_from_deterministic_tools"
            for snapshot in execution.state_history:
                if snapshot.get("node") in {"Response Generation", "END"}:
                    snapshot["final_answer"] = execution.answer
            return execution
        except Exception as exc:
            error = self._error_execution(exc, execution.tool_results, execution.intent)
            error.call_chain = execution.call_chain
            error.state_history = execution.state_history
            error.transaction_id = execution.transaction_id
            error.context_version = execution.context_version
            error.transaction_context = execution.transaction_context
            error.required_fields = execution.required_fields
            error.missing_fields = execution.missing_fields
            error.information_completeness = execution.information_completeness
            error.next_best_question = execution.next_best_question
            error.decision_result = execution.decision_result
            error.comparison = execution.comparison
            return error

    @staticmethod
    def _error_execution(
        exc: Exception,
        calls: list[ToolResult],
        intent: str,
    ) -> AgentExecution:
        """把 Provider 异常转换为可诊断但不泄露密钥的公开错误。"""

        if isinstance(exc, httpx.TimeoutException):
            code = "timeout"
            reason = "DeepSeek 响应超时，请稍后重试。"
        elif isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            code = f"http-{status}"
            reason_map = {
                400: "DeepSeek 拒绝了当前请求，请检查模型名称或请求格式。",
                401: "DeepSeek API Key 无效或未获授权。",
                402: "DeepSeek 账户余额不足。",
                429: "DeepSeek 请求过于频繁，已达到限流阈值。",
            }
            reason = reason_map.get(status, f"DeepSeek 服务返回 HTTP {status}。")
        elif isinstance(exc, httpx.NetworkError):
            code = "network"
            reason = "无法连接 DeepSeek 服务，请检查网络和 API 地址。"
        else:
            code = "invalid-response"
            reason = "DeepSeek 返回结果无法解析，请稍后重试。"
        return AgentExecution(
            answer=f"DeepSeek 本次调用失败：{reason}系统没有生成本地替代回答。",
            tool_results=calls,
            insufficient_data=True,
            mode=f"llm-error:{code}",
            intent=intent,
        )

    def run(self, message: str, customer_id: int | None, intent: IntentResult) -> AgentExecution:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(message, customer_id, intent.name)},
        ]
        calls: list[ToolResult] = []
        try:
            # 系统评价标准必须先读取当前确定性配置，再交给 LLM 做语言整理。
            # 这类问题不需要 customer_id，也不能退化为只查 RAG 静态文档。
            if intent.name == "risk_methodology":
                methodology = self.tools.execute("get_risk_evaluation_criteria", {})
                calls.append(methodology)
                if not methodology.success:
                    raise RuntimeError("风险评价标准 Tool 不可用")
                messages.append({
                    "role": "system",
                    "content": (
                        "以下是 get_risk_evaluation_criteria 确定性工具的完整返回。"
                        "请直接回答用户问题，使用清晰 Markdown，准确说明各层评价标准、当前启用规则、公式和人工决策边界；"
                        "不得声称缺少客户ID，不得补充工具中不存在的标准。\n"
                        + json.dumps(methodology.data, ensure_ascii=False, default=str)
                    ),
                })
                answer = self._generate_final_answer(messages)
                return AgentExecution(answer, calls, not bool(answer.strip()), f"llm:{self.provider.provider_name}", intent=intent.name)

            assistant = self.provider.complete(messages, self.tools.llm_specs())
            # 某些兼容模型偶尔先返回自然语言而没有 tool_calls。追加一次强约束重试，
            # 仍不符合要求时直接报错，不接受无业务证据的自由回答。
            if not assistant.get("tool_calls"):
                messages.append({
                    "role": "system",
                    "content": "你必须先调用至少一个最相关的受控 Tool，不得直接回答。请现在仅返回 Tool Calling。",
                })
                assistant = self.provider.complete(messages, self.tools.llm_specs())
            messages.append(assistant)
            # 基础框架限制为一轮工具调用，避免无上限循环和工具滥用。
            for call in assistant.get("tool_calls", [])[:6]:
                name = call.get("function", {}).get("name", "")
                arguments = json.loads(call.get("function", {}).get("arguments") or "{}")
                result = self.tools.execute(name, arguments)
                calls.append(result)
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", "unknown"),
                    "content": json.dumps(
                        {
                            "success": result.success,
                            "data": result.data if result.success else None,
                            "error": {"code": result.error_code, "message": result.error_message} if not result.success else None,
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                })

            # 风控解释必须有工具证据。模型两次都未调用工具时明确报错。
            if not calls:
                return AgentExecution(
                    answer="DeepSeek 未返回受控 Tool 调用，系统已拒绝无业务证据的自由回答，也没有生成本地替代回答。请重试或换一种更具体的问法。",
                    tool_results=[],
                    insufficient_data=True,
                    mode="llm-error:no-tool",
                    intent=intent.name,
                )

            answer = self._generate_final_answer(messages)
            return AgentExecution(answer, calls, not bool(answer.strip()), f"llm:{self.provider.provider_name}")
        except Exception as exc:
            return self._error_execution(exc, calls, intent.name)
