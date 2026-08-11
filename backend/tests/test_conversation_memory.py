"""Agent Conversation Memory 持久化、恢复、隔离与脱敏测试。"""

import json
from uuid import uuid4

from backend.app.core.database import SessionLocal
from backend.app.models import AgentConversation, AgentMessage
from backend.app.services.conversation_service import ConversationService


def unique_conversation(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def test_chat_persists_user_answer_and_safe_tool_calls(client):
    conversation_id = unique_conversation("memory-save")
    response = client.post(
        "/api/agent/chat",
        json={"message": "查询信用情况", "customer_id": 5, "conversation_id": conversation_id},
    )
    assert response.status_code == 200

    with SessionLocal() as db:
        conversation = db.query(AgentConversation).filter(AgentConversation.conversation_id == conversation_id).one()
        messages = (
            db.query(AgentMessage)
            .filter(AgentMessage.conversation_id == conversation.id)
            .order_by(AgentMessage.id)
            .all()
        )
        assert [item.role for item in messages] == ["user", "assistant"]
        assert messages[0].content == "查询信用情况"
        assert messages[0].tool_calls == []
        assert messages[1].content
        assert messages[1].tool_calls[0]["tool"] == "get_customer_credit_score"
        assert messages[1].tool_calls[0]["arguments"] == {"customer_id": 5}
        # 只保存工具元数据，不保存评分 Tool 的完整返回值。
        assert "data" not in messages[1].tool_calls[0]


def test_history_restores_conversation_and_customer_context(client):
    conversation_id = unique_conversation("memory-context")
    first = client.post(
        "/api/agent/chat",
        json={"message": "查询客户信息", "customer_id": 5, "conversation_id": conversation_id},
    )
    assert first.status_code == 200

    # 后续请求不再传 customer_id，Agent 应从 conversation_id 恢复为客户 5。
    second = client.post(
        "/api/agent/chat",
        json={"message": "那再查询信用情况", "customer_id": "", "conversation_id": conversation_id},
    )
    assert second.status_code == 200
    assert second.json()["data"]["tools_used"] == ["get_customer_credit_score"]
    assert second.json()["data"]["tools_called"][0]["arguments"]["customer_id"] == 5

    history = client.get(f"/api/agent/history/{conversation_id}")
    assert history.status_code == 200
    data = history.json()["data"]
    assert data["conversation_id"] == conversation_id
    assert data["customer_id"] == 5
    assert [item["role"] for item in data["messages"]] == ["user", "assistant", "user", "assistant"]
    assert data["messages"][-1]["tool_calls"][0]["tool"] == "get_customer_credit_score"

    with SessionLocal() as db:
        context = ConversationService(db).get_context(1, conversation_id)
        assert len(context) == 4
        assert context[-1].role == "assistant"


def test_history_is_scoped_by_merchant_and_user(client):
    conversation_id = unique_conversation("memory-scope")
    headers = {"X-User-ID": "roadshow-user"}
    created = client.post(
        "/api/agent/chat",
        headers=headers,
        json={"message": "查询客户信息", "customer_id": 5, "conversation_id": conversation_id},
    )
    assert created.status_code == 200
    assert client.get(f"/api/agent/history/{conversation_id}", headers=headers).status_code == 200
    assert client.get(f"/api/agent/history/{conversation_id}", headers={"X-User-ID": "another-user"}).status_code == 404
    assert client.get(
        f"/api/agent/history/{conversation_id}",
        headers={"X-User-ID": "roadshow-user", "X-Merchant-ID": "999"},
    ).status_code == 404


def test_sensitive_text_is_redacted_before_database_write(client):
    conversation_id = unique_conversation("memory-redaction")
    sensitive_message = (
        "查询客户信息，邮箱 alice@example.com，电话 +86 13800138000，"
        "注册号：CN-SECRET-9988，地址：浙江省义乌市稠州路88号；api_key=sk-secret-value"
    )
    response = client.post(
        "/api/agent/chat",
        headers={"X-User-ID": "person@example.com"},
        json={"message": sensitive_message, "customer_id": 5, "conversation_id": conversation_id},
    )
    assert response.status_code == 200

    history = client.get(
        f"/api/agent/history/{conversation_id}",
        headers={"X-User-ID": "person@example.com"},
    )
    assert history.status_code == 200
    serialized = json.dumps(history.json()["data"], ensure_ascii=False)
    for raw in ["alice@example.com", "13800138000", "CN-SECRET-9988", "浙江省义乌市稠州路88号", "sk-secret-value"]:
        assert raw not in serialized
    assert "已脱敏" in serialized

    with SessionLocal() as db:
        conversation = db.query(AgentConversation).filter(AgentConversation.conversation_id == conversation_id).one()
        stored = conversation.title + " " + " ".join(item.content for item in conversation.messages)
        assert "alice@example.com" not in stored
        assert conversation.user_id.startswith("user-")


def test_deleting_conversation_cascades_messages(client):
    conversation_id = unique_conversation("memory-delete")
    client.post(
        "/api/agent/chat",
        json={"message": "查询客户信息", "customer_id": 5, "conversation_id": conversation_id},
    )
    with SessionLocal() as db:
        internal_id = db.query(AgentConversation.id).filter(AgentConversation.conversation_id == conversation_id).scalar()
        assert db.query(AgentMessage).filter(AgentMessage.conversation_id == internal_id).count() == 2

    deleted = client.delete(f"/api/agent/conversations/{conversation_id}")
    assert deleted.status_code == 200
    with SessionLocal() as db:
        assert db.query(AgentConversation).filter(AgentConversation.conversation_id == conversation_id).count() == 0
        assert db.query(AgentMessage).filter(AgentMessage.conversation_id == internal_id).count() == 0
