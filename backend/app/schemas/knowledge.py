"""风控知识库管理与检索 API Schema。"""

from typing import Literal

from pydantic import BaseModel, Field


KnowledgeCategory = Literal[
    "risk_case",
    "yiwu_market_experience",
    "contract_risk_rule",
    "risk_operation_standard",
]


class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    content: str = Field(min_length=20, max_length=50_000)
    category: KnowledgeCategory


class KnowledgeIngestResponse(BaseModel):
    title: str
    category: KnowledgeCategory
    chunk_count: int
    knowledge_ids: list[int]
    embedding_provider: str
    embedding_dimensions: int


class KnowledgeSearchItem(BaseModel):
    knowledge_id: int
    title: str
    content: str
    category: KnowledgeCategory
    similarity: float


class KnowledgeSearchResponse(BaseModel):
    query: str
    source_kind: Literal["unstructured_knowledge"]
    retrieval_method: str
    embedding_provider: str
    items: list[KnowledgeSearchItem]
