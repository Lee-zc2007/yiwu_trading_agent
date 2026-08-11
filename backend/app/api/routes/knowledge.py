"""非结构化风控知识的入库与检索 API。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...schemas.common import ApiResponse
from ...schemas.knowledge import KnowledgeCategory, KnowledgeDocumentCreate, KnowledgeIngestResponse, KnowledgeSearchResponse
from ...services.knowledge_base import KnowledgeBaseService


router = APIRouter(prefix="/api/knowledge", tags=["风控知识库 RAG"])


@router.post("/documents", response_model=ApiResponse[KnowledgeIngestResponse], status_code=201)
def ingest_document(payload: KnowledgeDocumentCreate, db: Session = Depends(get_db)):
    """文档 -> 文本切分 -> Embedding -> pgvector 存储。"""

    result = KnowledgeBaseService(db).ingest_document(payload.title, payload.content, payload.category)
    db.commit()
    return {"data": result, "message": f"知识文档已切分为 {result['chunk_count']} 个向量块"}


@router.get("/search", response_model=ApiResponse[KnowledgeSearchResponse])
def search_knowledge(
    q: str = Query(min_length=1, max_length=1000),
    category: KnowledgeCategory | None = Query(default=None),
    limit: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """直接验证 RAG 召回；不会查询客户、订单、评分或风险事件表。"""

    return {"data": KnowledgeBaseService(db).search(q, category, limit)}
