from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...agent import AgentService
from ...agent.schemas import ToolContext
from ...core.database import get_db
from ...schemas.agent import AgentChatRequest, AgentChatResponse
from ...schemas.common import ApiResponse
from ..dependencies import get_merchant_id


router = APIRouter(prefix="/api/agent", tags=["AI Agent"])


@router.post("/chat", response_model=ApiResponse[AgentChatResponse])
def chat(payload: AgentChatRequest, merchant_id: int = Depends(get_merchant_id), db: Session = Depends(get_db)):
    response = AgentService().chat(ToolContext(db, merchant_id), payload.message, payload.customer_id, payload.conversation_id)
    db.commit()
    return {"data": response}
