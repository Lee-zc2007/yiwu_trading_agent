"""基础会话管理。

本模块保留线程安全的进程内实现，供不经过 API 的单元调用使用。正式 API 注入
``services.conversation_service.ConversationService`` 实现数据库持久化。
"""

from datetime import UTC, datetime
from threading import RLock
from typing import Any, Protocol
from uuid import uuid4

from ..schemas.agent import AgentEvidence, ConversationMessage, ConversationResponse, ConversationSummary


def utc_now() -> datetime:
    return datetime.now(UTC)


class ConversationStore(Protocol):
    """Agent Service 依赖的会话存储协议，不暴露数据库类型。"""

    def ensure(self, merchant_id: int, conversation_id: str, customer_id: int | None, message: str) -> ConversationResponse: ...
    def append_message(
        self,
        merchant_id: int,
        conversation_id: str,
        role: str,
        content: str,
        tools_used: list[str] | None = None,
        evidence: list[AgentEvidence] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None: ...
    def resolve_customer_id(self, merchant_id: int, conversation_id: str) -> int | None: ...


class ConversationManager:
    """线程安全的会话仓库，对外只返回 Pydantic 数据副本。"""

    def __init__(self):
        self._items: dict[tuple[int, str], ConversationResponse] = {}
        self._lock = RLock()

    def create(self, merchant_id: int, title: str = "新会话", customer_id: int | None = None, conversation_id: str = "") -> ConversationResponse:
        with self._lock:
            identifier = conversation_id.strip() or uuid4().hex
            key = (merchant_id, identifier)
            existing = self._items.get(key)
            if existing:
                if customer_id and not existing.customer_id:
                    existing.customer_id = customer_id
                    existing.updated_at = utc_now()
                return existing.model_copy(deep=True)
            now = utc_now()
            conversation = ConversationResponse(
                conversation_id=identifier,
                merchant_id=merchant_id,
                title=title.strip() or "新会话",
                customer_id=customer_id,
                created_at=now,
                updated_at=now,
                messages=[],
            )
            self._items[key] = conversation
            return conversation.model_copy(deep=True)

    def ensure(self, merchant_id: int, conversation_id: str, customer_id: int | None, message: str) -> ConversationResponse:
        title = message.strip()[:40] or "新会话"
        return self.create(merchant_id=merchant_id, title=title, customer_id=customer_id, conversation_id=conversation_id)

    def append_message(
        self,
        merchant_id: int,
        conversation_id: str,
        role: str,
        content: str,
        tools_used: list[str] | None = None,
        evidence: list[AgentEvidence] | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        with self._lock:
            conversation = self._items.get((merchant_id, conversation_id))
            if not conversation:
                raise KeyError("会话不存在")
            conversation.messages.append(
                ConversationMessage(
                    role=role,
                    content=content,
                    created_at=utc_now(),
                    tool_calls=tool_calls or [],
                    tools_used=tools_used or [],
                    evidence=evidence or [],
                )
            )
            conversation.updated_at = utc_now()

    def get_context(self, merchant_id: int, conversation_id: str, limit: int = 20) -> list[ConversationMessage]:
        conversation = self.get(merchant_id, conversation_id)
        return conversation.messages[-max(1, min(limit, 100)):] if conversation else []

    def resolve_customer_id(self, merchant_id: int, conversation_id: str) -> int | None:
        conversation = self.get(merchant_id, conversation_id)
        if not conversation:
            return None
        if conversation.customer_id:
            return conversation.customer_id
        for message in reversed(conversation.messages):
            for call in reversed(message.tool_calls):
                arguments = call.get("arguments") or {}
                for key in ("customer_id", "customer_id_a", "customer_id_b"):
                    value = arguments.get(key)
                    if isinstance(value, int) and value > 0:
                        return value
        return None

    def get(self, merchant_id: int, conversation_id: str) -> ConversationResponse | None:
        with self._lock:
            item = self._items.get((merchant_id, conversation_id))
            return item.model_copy(deep=True) if item else None

    def list(self, merchant_id: int) -> list[ConversationSummary]:
        with self._lock:
            rows = sorted((item for item in self._items.values() if item.merchant_id == merchant_id), key=lambda item: item.updated_at, reverse=True)
            return [
                ConversationSummary(
                    conversation_id=item.conversation_id,
                    merchant_id=item.merchant_id,
                    title=item.title,
                    customer_id=item.customer_id,
                    message_count=len(item.messages),
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                )
                for item in rows
            ]

    def delete(self, merchant_id: int, conversation_id: str) -> bool:
        with self._lock:
            return self._items.pop((merchant_id, conversation_id), None) is not None


# 单进程共享实例。未来替换存储实现时，API 和 AgentService 无需改变。
conversation_manager = ConversationManager()
