import json

import httpx

from ..core.config import settings
from .mock_agent import MockAgent
from .prompts import SYSTEM_PROMPT
from .schemas import ToolContext, ToolResult
from .tools import TOOL_REGISTRY


class LLMAgent:
    """OpenAI-compatible Tool Calling 适配层；任何失败都会安全退回 Mock。"""

    tool_specs = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": function.__doc__ or name,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_id": {"type": "integer"},
                        "order_id": {"type": "integer"},
                        "event_id": {"type": "integer"},
                        "customer_id_a": {"type": "integer"},
                        "customer_id_b": {"type": "integer"},
                    },
                    "additionalProperties": False,
                },
            },
        }
        for name, function in TOOL_REGISTRY.items()
    ]

    def run(self, context: ToolContext, message: str, customer_id: int | None) -> tuple[str, list[ToolResult], bool]:
        if not settings.llm_api_key:
            return MockAgent().run(context, message, customer_id)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": f"customer_id={customer_id}\n{message}"}]
        calls: list[ToolResult] = []
        try:
            with httpx.Client(timeout=25) as client:
                first = client.post(f"{settings.llm_base_url.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {settings.llm_api_key}"}, json={"model": settings.llm_model, "messages": messages, "tools": self.tool_specs, "tool_choice": "auto"})
                first.raise_for_status(); assistant = first.json()["choices"][0]["message"]; messages.append(assistant)
                for call in assistant.get("tool_calls", []):
                    name = call["function"]["name"]
                    if name not in TOOL_REGISTRY: continue
                    arguments = json.loads(call["function"].get("arguments") or "{}")
                    result = TOOL_REGISTRY[name](context, **arguments); calls.append(result)
                    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result.data, ensure_ascii=False, default=str)})
                if calls:
                    final = client.post(f"{settings.llm_base_url.rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {settings.llm_api_key}"}, json={"model": settings.llm_model, "messages": messages})
                    final.raise_for_status(); answer = final.json()["choices"][0]["message"]["content"]
                else: answer = assistant.get("content") or "数据不足，无法回答。"
            return answer, calls, False
        except Exception:
            answer, fallback_calls, insufficient = MockAgent().run(context, message, customer_id)
            return "LLM 服务暂不可用，已切换到本地 Mock Agent。\n\n" + answer, fallback_calls, insufficient
