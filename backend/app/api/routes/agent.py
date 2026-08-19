"""AI Agent 与会话管理 API。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...agent import AgentService
from ...core.database import get_db
from ...schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    ConversationCreateRequest,
    ConversationResponse,
    ConversationSummary,
)
from ...schemas.common import ApiResponse
from ...services.agent_data import SqlAlchemyAgentDataGateway
from ...services.conversation_service import ConversationService
from ...services.decision_context import DecisionContextService
from ..dependencies import get_merchant_id, get_user_id


router = APIRouter(prefix="/api/agent", tags=["AI Agent"])


@router.post("/chat", response_model=ApiResponse[AgentChatResponse])
def chat(
    payload: AgentChatRequest,
    merchant_id: int = Depends(get_merchant_id),
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """统一聊天入口：意图识别 -> 只读工具 -> 业务证据 -> 回答。"""

    gateway = SqlAlchemyAgentDataGateway(db, merchant_id)
    memory = ConversationService(db, user_id)
    response = AgentService(
        gateway=gateway,
        merchant_id=merchant_id,
        conversations=memory,
        decision_contexts=DecisionContextService(db, user_id),
    ).chat(
        message=payload.message,
        customer_id=payload.customer_id,
        conversation_id=payload.conversation_id,
    )
    db.commit()
    return {"data": response}


@router.post("/conversations", response_model=ApiResponse[ConversationResponse], status_code=201)
def create_conversation(
    payload: ConversationCreateRequest,
    merchant_id: int = Depends(get_merchant_id),
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    conversation = ConversationService(db, user_id).create(merchant_id, payload.title, payload.customer_id)
    db.commit()
    return {"data": conversation, "message": "Agent 会话已创建"}


@router.get("/conversations", response_model=ApiResponse[list[ConversationSummary]])
def list_conversations(
    merchant_id: int = Depends(get_merchant_id),
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    return {"data": ConversationService(db, user_id).list(merchant_id)}


@router.get("/conversations/{conversation_id}", response_model=ApiResponse[ConversationResponse])
def get_conversation(
    conversation_id: str,
    merchant_id: int = Depends(get_merchant_id),
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    conversation = ConversationService(db, user_id).get(merchant_id, conversation_id)
    if not conversation:
        raise HTTPException(404, "Agent 会话不存在")
    return {"data": conversation}


@router.get("/history/{conversation_id}", response_model=ApiResponse[ConversationResponse])
def get_conversation_history(
    conversation_id: str,
    merchant_id: int = Depends(get_merchant_id),
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    """根据 conversation_id 恢复当前商户、当前用户的脱敏对话与工具调用。"""

    conversation = ConversationService(db, user_id).history(merchant_id, conversation_id)
    if not conversation:
        raise HTTPException(404, "Agent 会话不存在")
    return {"data": conversation}


@router.delete("/conversations/{conversation_id}", response_model=ApiResponse[dict])
def delete_conversation(
    conversation_id: str,
    merchant_id: int = Depends(get_merchant_id),
    user_id: str = Depends(get_user_id),
    db: Session = Depends(get_db),
):
    if not ConversationService(db, user_id).delete(merchant_id, conversation_id):
        raise HTTPException(404, "Agent 会话不存在")
    db.commit()
    return {"data": {"conversation_id": conversation_id}, "message": "Agent 会话已删除"}
