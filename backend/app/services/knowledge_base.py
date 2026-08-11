"""风控知识库的切分、Embedding、pgvector 入库与相似度检索服务。

本模块只处理外贸案例、义乌市场经验、合同规则和风控规范等非结构化知识。
客户、交易、信用评分、风险事件等结构化业务数据仍由原有 SQL 服务查询，禁止
复制进向量数据库。
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from hashlib import blake2b
import math
import re
from typing import Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import KnowledgeBase


KNOWLEDGE_CATEGORIES = {
    "risk_case",
    "yiwu_market_experience",
    "contract_risk_rule",
    "risk_operation_standard",
}


class EmbeddingProvider(Protocol):
    """本地与远程 Embedding Provider 的统一接口。"""

    provider_name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalHashEmbeddingProvider:
    """无需 API Key 的确定性多语种哈希向量，用于离线路演与测试。

    该实现不是生成式模型，也不会读取业务数据库。它把中英文 token 和中文
    n-gram 映射到固定维度，并执行 L2 归一化，以便使用余弦距离检索。
    """

    provider_name = "local-hash"

    def __init__(self, dimensions: int = 384):
        if dimensions < 32:
            raise ValueError("Embedding 维度不能小于 32")
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        tokens = self._tokens(text)
        vector = [0.0] * self.dimensions
        for token, count in Counter(tokens).items():
            digest = blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimensions
            vector[index] += 1.0 + math.log(count)
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        normalized = re.sub(r"\s+", "", text.lower())
        ascii_tokens = re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower())
        chinese = "".join(re.findall(r"[\u3400-\u9fff]", normalized))
        chinese_tokens = list(chinese)
        chinese_tokens.extend(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
        chinese_tokens.extend(chinese[index:index + 3] for index in range(max(0, len(chinese) - 2)))
        return ascii_tokens + chinese_tokens


class OpenAICompatibleEmbeddingProvider:
    """OpenAI-compatible `/embeddings` Provider，可用于 GPT、Qwen 兼容服务。"""

    provider_name = "openai-compatible"

    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int, timeout_seconds: float = 30):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError("未配置 Embedding API Key")
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.base_url}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": texts, "dimensions": self.dimensions},
            )
            response.raise_for_status()
            rows = sorted(response.json().get("data", []), key=lambda item: item["index"])
        embeddings = [list(map(float, item["embedding"])) for item in rows]
        if len(embeddings) != len(texts) or any(len(item) != self.dimensions for item in embeddings):
            raise RuntimeError("Embedding 服务返回数量或维度不符合配置")
        return embeddings


def build_embedding_provider() -> EmbeddingProvider:
    """根据配置创建 Provider；默认离线模式不会访问外部网络。"""

    provider = settings.embedding_provider.strip().lower()
    if provider in {"openai", "openai-compatible", "qwen-compatible"}:
        return OpenAICompatibleEmbeddingProvider(
            api_key=settings.embedding_api_key or settings.llm_api_key,
            base_url=settings.embedding_base_url,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )
    return LocalHashEmbeddingProvider(settings.embedding_dimensions)


def split_text(content: str, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """按标点优先切分长文档，并保留少量重叠上下文。"""

    size = chunk_size or settings.knowledge_chunk_size
    shared = settings.knowledge_chunk_overlap if overlap is None else overlap
    if size < 100 or shared < 0 or shared >= size:
        raise ValueError("文本切分参数无效")
    normalized = re.sub(r"[ \t]+", " ", content).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + size)
        if end < len(normalized):
            search_start = start + int(size * 0.55)
            candidates = [normalized.rfind(mark, search_start, end) for mark in ("\n", "。", "；", "！", "？", ".")]
            boundary = max(candidates)
            if boundary > start:
                end = boundary + 1
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(start + 1, end - shared)
    return chunks


class KnowledgeBaseService:
    """非结构化知识服务；PostgreSQL 使用 pgvector，SQLite 仅作兼容测试。"""

    def __init__(self, db: Session, embedding_provider: EmbeddingProvider | None = None):
        self.db = db
        self.embedding_provider = embedding_provider or build_embedding_provider()

    def ingest_document(self, title: str, content: str, category: str) -> dict:
        """切分并向量化一篇文档；事务提交由 API/启动流程统一控制。"""

        normalized_title = title.strip()
        normalized_content = content.strip()
        if not normalized_title or not normalized_content:
            raise ValueError("知识文档标题和内容不能为空")
        if category not in KNOWLEDGE_CATEGORIES:
            raise ValueError("知识分类不在允许列表中")
        chunks = split_text(normalized_content)
        if not chunks:
            raise ValueError("知识文档切分后没有有效内容")
        embeddings = self.embedding_provider.embed(chunks)
        rows = [
            KnowledgeBase(title=normalized_title, content=chunk, embedding=embedding, category=category)
            for chunk, embedding in zip(chunks, embeddings, strict=True)
        ]
        self.db.add_all(rows)
        self.db.flush()
        return {
            "title": normalized_title,
            "category": category,
            "chunk_count": len(rows),
            "knowledge_ids": [item.id for item in rows],
            "embedding_provider": self.embedding_provider.provider_name,
            "embedding_dimensions": self.embedding_provider.dimensions,
        }

    def search(self, query: str, category: str | None = None, limit: int | None = None) -> dict:
        """检索非结构化知识，不查询或拼接任何交易表。"""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("知识检索问题不能为空")
        if category is not None and category not in KNOWLEDGE_CATEGORIES:
            raise ValueError("知识分类不在允许列表中")
        top_k = max(1, min(limit or settings.knowledge_top_k, 10))
        query_vector = self.embedding_provider.embed([normalized_query])[0]
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            items = self._search_pgvector(query_vector, category, top_k)
            retrieval_method = "pgvector_cosine_hnsw"
        else:
            items = self._search_sqlite_fallback(query_vector, category, top_k)
            retrieval_method = "sqlite_cosine_compatibility"
        return {
            "query": normalized_query,
            "source_kind": "unstructured_knowledge",
            "retrieval_method": retrieval_method,
            "embedding_provider": self.embedding_provider.provider_name,
            "items": items,
        }

    def _search_pgvector(self, vector: list[float], category: str | None, limit: int) -> list[dict]:
        distance = KnowledgeBase.embedding.cosine_distance(vector)
        statement = select(KnowledgeBase, distance.label("distance"))
        if category:
            statement = statement.where(KnowledgeBase.category == category)
        rows = self.db.execute(statement.order_by(distance).limit(limit)).all()
        return self._format_rows(((item, 1.0 - float(distance_value)) for item, distance_value in rows))

    def _search_sqlite_fallback(self, vector: list[float], category: str | None, limit: int) -> list[dict]:
        statement = select(KnowledgeBase)
        if category:
            statement = statement.where(KnowledgeBase.category == category)
        scored = [
            (item, self._cosine_similarity(vector, list(item.embedding)))
            for item in self.db.scalars(statement).all()
        ]
        scored.sort(key=lambda row: row[1], reverse=True)
        return self._format_rows(scored[:limit])

    @staticmethod
    def _cosine_similarity(first: Sequence[float], second: Sequence[float]) -> float:
        if len(first) != len(second):
            return 0.0
        first_norm = math.sqrt(sum(float(value) ** 2 for value in first))
        second_norm = math.sqrt(sum(float(value) ** 2 for value in second))
        if not first_norm or not second_norm:
            return 0.0
        return sum(float(a) * float(b) for a, b in zip(first, second, strict=True)) / (first_norm * second_norm)

    @staticmethod
    def _format_rows(rows) -> list[dict]:
        return [
            {
                "knowledge_id": item.id,
                "title": item.title,
                "content": item.content,
                "category": item.category,
                "similarity": round(max(-1.0, min(1.0, float(similarity))), 4),
            }
            for item, similarity in rows
            if float(similarity) >= settings.knowledge_min_similarity
        ]


__all__ = [
    "EmbeddingProvider",
    "KnowledgeBaseService",
    "KNOWLEDGE_CATEGORIES",
    "LocalHashEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
    "build_embedding_provider",
    "split_text",
]
