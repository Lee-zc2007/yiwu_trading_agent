"""可扩展 LLM Provider 接口与 Tool Calling Agent。

当前提供 OpenAI-compatible 实现，可连接 GPT 及提供兼容接口的 Qwen 服务。未来
Claude、原生 Qwen 等适配器只需实现 ``LLMProvider.complete``，无需修改工具层或
Agent Service。
"""

import json
from typing import Protocol

import httpx

from .mock_agent import MockAgent
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schemas import AgentExecution, IntentResult, ToolResult
from .tools import AgentToolRegistry


class LLMProvider(Protocol):
    """GPT、Claude、Qwen 等模型适配器的最小接口。"""

    provider_name: str

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...


class OpenAICompatibleProvider:
    """OpenAI Chat Completions 兼容接口实现。"""

    provider_name = "openai-compatible"

    def __init__(self, api_key: str, base_url: str, model: str, timeout_seconds: float = 25):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def complete(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload: dict = {"model": self.model, "messages": messages}
        if tools:
            payload.update({"tools": tools, "tool_choice": "auto"})
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]


class LLMAgent:
    """使用 Provider 选择工具；失败或无证据回答时安全回退 Mock。"""

    def __init__(self, tools: AgentToolRegistry, provider: LLMProvider, fallback: MockAgent):
        self.tools = tools
        self.provider = provider
        self.fallback = fallback

    def run(self, message: str, customer_id: int | None, intent: IntentResult) -> AgentExecution:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(message, customer_id, intent.name)},
        ]
        calls: list[ToolResult] = []
        try:
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

            # 风控解释必须有工具证据。模型未调用工具时不接受其自由回答。
            if not calls:
                fallback = self.fallback.run(message, customer_id, intent)
                fallback.mode = "mock-fallback"
                return fallback

            final_message = self.provider.complete(messages)
            answer = final_message.get("content") or "数据不足，无法形成有证据的回答。"
            return AgentExecution(answer, calls, not bool(answer.strip()), f"llm:{self.provider.provider_name}")
        except Exception:
            fallback = self.fallback.run(message, customer_id, intent)
            fallback.answer = "LLM 服务暂不可用，已切换到本地 Mock Agent。\n\n" + fallback.answer
            fallback.mode = "mock-fallback"
            return fallback
