"""Agent Conversation Memory 数据库服务。

本服务位于 Agent 包之外，负责数据库持久化、商户/用户隔离与入库前脱敏。
Agent 本身只依赖 ConversationStore 协议，不接触 ORM 或数据库 Session。
"""

from hashlib import sha256
import re
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import AgentConversation, AgentMessage
from ..models.entities import utc_now
from ..schemas.agent import ConversationMessage, ConversationResponse, ConversationSummary


EMAIL_PATTERN = re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s()\-]{7,}\d)(?!\w)")
LONG_NUMBER_PATTERN = re.compile(r"(?<!\d)\d{8,32}(?!\d)")
SECRET_PATTERN = re.compile(
    r"(?i)(api[_\s-]?key|access[_\s-]?token|secret|password|token|密码|密钥)\s*[:=：]\s*[^\s,，;；]+"
)
SENSITIVE_FIELD_PATTERN = re.compile(
    r"(?i)(身份证|护照号?|税号|注册号|银行账号?|银行卡号?|收款账号?|beneficiary\s*account)\s*[:=：]?\s*[^\s,，;；]+"
)
ADDRESS_PATTERN = re.compile(
    r"(?i)(收货地址|公司地址|联系地址|住址|地址|shipping\s*address|address)\s*[:=：]?\s*[^\n,，;；]{4,160}"
)

SAFE_TOOL_ARGUMENTS = {
    "customer_id",
    "customer_id_a",
    "customer_id_b",
    "order_id",
    "event_id",
    "limit",
}


def redact_sensitive_text(value: str) -> str:
    """移除会话文本中的常见直接标识符和凭证，不保留敏感原文。"""

    text = str(value or "")[:10_000]
    text = SECRET_PATTERN.sub(lambda match: f"{match.group(1)}：[敏感凭证已脱敏]", text)
    text = EMAIL_PATTERN.sub("[邮箱已脱敏]", text)
    text = SENSITIVE_FIELD_PATTERN.sub(lambda match: f"{match.group(1)}：[敏感编号已脱敏]", text)
    text = ADDRESS_PATTERN.sub(lambda match: f"{match.group(1)}：[地址已脱敏]", text)
    text = PHONE_PATTERN.sub("[电话已脱敏]", text)
    text = LONG_NUMBER_PATTERN.sub("[长数字已脱敏]", text)
    return text.strip()


def normalize_user_id(value: str) -> str:
    """只保存非敏感用户标识；邮箱或复杂标识改为不可逆短哈希。"""

    candidate = str(value or "demo-user").strip()[:240]
    if re.fullmatch(r"[A-Za-z0-9._-]{1,120}", candidate):
        return candidate
    digest = sha256(candidate.encode("utf-8")).hexdigest()[:20]
    return f"user-{digest}"


def sanitize_tool_calls(tool_calls: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """仅保存白名单 Tool 元数据与非敏感 ID 参数，不保存 Tool 完整返回值。"""

    safe_calls: list[dict[str, Any]] = []
    for raw in (tool_calls or [])[:20]:
        name = str(raw.get("tool") or raw.get("name") or "")[:120]
        if not name:
            continue
        raw_arguments = raw.get("arguments") if isinstance(raw.get("arguments"), dict) else {}
        arguments = {
            key: value
            for key, value in raw_arguments.items()
            if key in SAFE_TOOL_ARGUMENTS and isinstance(value, (int, float, bool, type(None)))
        }
        safe_calls.append({
            "tool": name,
            "arguments": arguments,
            "success": bool(raw.get("success", True)),
            # 不保存可能包含企业名称、评分、金额等业务内容的原始摘要。
            "summary": "工具调用成功" if bool(raw.get("success", True)) else "工具调用失败",
            "error_code": str(raw.get("error_code") or "")[:80] or None,
        })
    return safe_calls


class ConversationService:
    """SQLAlchemy ConversationStore 实现，所有查询均按商户和用户隔离。"""

    def __init__(self, db: Session, user_id: str = "demo-user"):
        self.db = db
        self.user_id = normalize_user_id(user_id)

    def create(
        self,
        merchant_id: int,
        title: str = "新会话",
        customer_id: int | None = None,
        conversation_id: str = "",
    ) -> ConversationResponse:
        identifier = conversation_id.strip()[:120] or uuid4().hex
        existing = self._conversation(merchant_id, identifier)
        if existing:
            if customer_id and not existing.customer_id:
                existing.customer_id = customer_id
                existing.updated_at = utc_now()
                self.db.flush()
            return self._response(existing)
        conversation = AgentConversation(
            merchant_id=merchant_id,
            user_id=self.user_id,
            conversation_id=identifier,
            title=redact_sensitive_text(title or "新会话")[:120] or "新会话",
            customer_id=customer_id,
        )
        self.db.add(conversation)
        self.db.flush()
        return self._response(conversation)

    def ensure(self, merchant_id: int, conversation_id: str, customer_id: int | None, message: str) -> ConversationResponse:
        title = redact_sensitive_text(message)[:40] or "新会话"
        return self.create(merchant_id, title, customer_id, conversation_id)

    def append_message(
        self,
        merchant_id: int,
        conversation_id: str,
        role: str,
        content: str,
        tools_used: list[str] | None = None,
        evidence: list | None = None,
        tool_calls: list[dict[str, Any]] | None = None,
    ) -> None:
        del tools_used, evidence  # 完整工具结果和证据正文不进入会话表。
        conversation = self._conversation(merchant_id, conversation_id)
        if not conversation:
            raise KeyError("会话不存在")
        safe_role = role if role in {"user", "assistant", "system", "tool"} else "assistant"
        message = AgentMessage(
            conversation_id=conversation.id,
            role=safe_role,
            content=redact_sensitive_text(content),
            tool_calls=sanitize_tool_calls(tool_calls),
        )
        self.db.add(message)
        conversation.updated_at = utc_now()
        self.db.flush()

    def get(self, merchant_id: int, conversation_id: str) -> ConversationResponse | None:
        conversation = self._conversation(merchant_id, conversation_id)
        return self._response(conversation) if conversation else None

    def history(self, merchant_id: int, conversation_id: str) -> ConversationResponse | None:
        """按 conversation_id 恢复完整脱敏对话。"""

        return self.get(merchant_id, conversation_id)

    def get_context(self, merchant_id: int, conversation_id: str, limit: int = 20) -> list[ConversationMessage]:
        """返回最近上下文，供后续意图识别或模型 Prompt 使用。"""

        conversation = self._conversation(merchant_id, conversation_id)
        if not conversation:
            return []
        rows = (
            self.db.query(AgentMessage)
            .filter(AgentMessage.conversation_id == conversation.id)
            .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
            .limit(max(1, min(limit, 100)))
            .all()
        )
        return [self._message(item) for item in reversed(rows)]

    def resolve_customer_id(self, merchant_id: int, conversation_id: str) -> int | None:
        """恢复会话客户上下文；只读取会话元数据和安全 Tool 参数。"""

        conversation = self._conversation(merchant_id, conversation_id)
        if not conversation:
            return None
        if conversation.customer_id:
            return conversation.customer_id
        rows = (
            self.db.query(AgentMessage)
            .filter(AgentMessage.conversation_id == conversation.id)
            .order_by(AgentMessage.created_at.desc(), AgentMessage.id.desc())
            .all()
        )
        for row in rows:
            for call in reversed(row.tool_calls or []):
                arguments = call.get("arguments") or {}
                for key in ("customer_id", "customer_id_a", "customer_id_b"):
                    value = arguments.get(key)
                    if isinstance(value, int) and value > 0:
                        return value
        return None

    def list(self, merchant_id: int) -> list[ConversationSummary]:
        rows = (
            self.db.query(AgentConversation, func.count(AgentMessage.id))
            .outerjoin(AgentMessage, AgentMessage.conversation_id == AgentConversation.id)
            .filter(AgentConversation.merchant_id == merchant_id, AgentConversation.user_id == self.user_id)
            .group_by(AgentConversation.id)
            .order_by(AgentConversation.updated_at.desc())
            .all()
        )
        return [
            ConversationSummary(
                conversation_id=item.conversation_id,
                merchant_id=item.merchant_id,
                user_id=item.user_id,
                title=item.title,
                customer_id=item.customer_id,
                message_count=int(count),
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item, count in rows
        ]

    def delete(self, merchant_id: int, conversation_id: str) -> bool:
        conversation = self._conversation(merchant_id, conversation_id)
        if not conversation:
            return False
        self.db.delete(conversation)
        self.db.flush()
        return True

    def _conversation(self, merchant_id: int, conversation_id: str) -> AgentConversation | None:
        if not conversation_id:
            return None
        return (
            self.db.query(AgentConversation)
            .filter(
                AgentConversation.merchant_id == merchant_id,
                AgentConversation.user_id == self.user_id,
                AgentConversation.conversation_id == conversation_id,
            )
            .first()
        )

    def _response(self, item: AgentConversation) -> ConversationResponse:
        rows = (
            self.db.query(AgentMessage)
            .filter(AgentMessage.conversation_id == item.id)
            .order_by(AgentMessage.created_at, AgentMessage.id)
            .all()
        )
        return ConversationResponse(
            conversation_id=item.conversation_id,
            merchant_id=item.merchant_id,
            user_id=item.user_id,
            title=item.title,
            customer_id=item.customer_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            messages=[self._message(row) for row in rows],
        )

    @staticmethod
    def _message(item: AgentMessage) -> ConversationMessage:
        calls = item.tool_calls or []
        return ConversationMessage(
            id=item.id,
            role=item.role,
            content=item.content,
            created_at=item.created_at,
            tool_calls=calls,
            tools_used=[call["tool"] for call in calls if call.get("tool")],
            evidence=[],
        )


__all__ = ["ConversationService", "redact_sensitive_text", "sanitize_tool_calls", "normalize_user_id"]
