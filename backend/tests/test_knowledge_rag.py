"""pgvector 知识库、RAG Tool 与结构化数据边界测试。"""

from sqlalchemy import inspect

from backend.app.agent.graph import AgentDecisionGraph
from backend.app.agent.tools import AgentToolRegistry
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.models import KnowledgeBase, Transaction
from backend.app.services.agent_data import SqlAlchemyAgentDataGateway
from backend.app.services.knowledge_base import KnowledgeBaseService, LocalHashEmbeddingProvider, split_text


def test_text_split_and_local_embedding_are_deterministic():
    content = "。".join(["付款账户变化后应通过原联系方式确认"] * 40)
    chunks = split_text(content, chunk_size=120, overlap=20)
    assert len(chunks) > 2
    provider = LocalHashEmbeddingProvider(64)
    first = provider.embed([chunks[0]])[0]
    second = provider.embed([chunks[0]])[0]
    assert first == second
    assert len(first) == 64
    assert abs(sum(value * value for value in first) - 1.0) < 1e-6


def test_seeded_knowledge_search_uses_only_unstructured_table(client):
    with SessionLocal() as db:
        transaction_count = db.query(Transaction).count()
        result = KnowledgeBaseService(db).search(
            "义乌市场遇到付款账户突然变更时应该怎么核验",
            category="yiwu_market_experience",
            limit=3,
        )

        assert result["source_kind"] == "unstructured_knowledge"
        assert result["retrieval_method"] == "sqlite_cosine_compatibility"
        assert result["items"]
        assert result["items"][0]["category"] == "yiwu_market_experience"
        assert db.query(Transaction).count() == transaction_count
        columns = {item["name"] for item in inspect(db.bind).get_columns("knowledge_base")}
        assert columns == {"id", "title", "content", "embedding", "category", "created_at"}
        assert db.query(KnowledgeBase).filter(KnowledgeBase.content.contains("TG-05-")).count() == 0


def test_search_risk_knowledge_tool_has_schema_and_evidence(client):
    with SessionLocal() as db:
        tools = AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1))
        result = tools.execute("search_risk_knowledge", {
            "query": "合同应如何约定定金尾款和货权转移",
            "category": "contract_risk_rule",
            "limit": 2,
        })

    assert result.success
    assert result.data["source_kind"] == "unstructured_knowledge"
    assert result.data["items"]
    assert all(item.source_type == "knowledge_chunk" for item in result.evidence)
    invalid = tools.execute("search_risk_knowledge", {"query": "合同", "sql": "SELECT * FROM transactions"})
    assert invalid.success is False
    assert invalid.error_code == "TOOL_INPUT_INVALID"


def test_agent_distinguishes_pure_rag_from_structured_risk_analysis(client):
    with SessionLocal() as db:
        graph = AgentDecisionGraph(AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1)))
        knowledge = graph.run("义乌市场付款账户变化有哪些经验", None)
        combined = graph.run("结合义乌市场经验分析为什么这个客户风险高", 5)

    assert knowledge.intent == "knowledge_search"
    assert [item.tool for item in knowledge.tool_results] == ["search_risk_knowledge"]
    assert "非结构化知识（RAG）" in knowledge.answer
    combined_tools = [item.tool for item in combined.tool_results]
    assert "get_customer_transactions" in combined_tools
    assert "get_order_risk_analysis" in combined_tools
    assert "search_risk_knowledge" in combined_tools
    assert "结构化业务事实（SQL 服务）" in combined.answer
    assert "非结构化知识参考（RAG，不是当前客户事实）" in combined.answer


def test_knowledge_document_api_splits_and_searches(client):
    content = "合同变更应由授权人员书面确认。" * 45
    created = client.post("/api/knowledge/documents", json={
        "title": "演示合同变更规范",
        "content": content,
        "category": "contract_risk_rule",
    })
    assert created.status_code == 201
    assert created.json()["data"]["chunk_count"] >= 2

    searched = client.get("/api/knowledge/search", params={
        "q": "合同变更如何确认",
        "category": "contract_risk_rule",
        "limit": 5,
    })
    assert searched.status_code == 200
    data = searched.json()["data"]
    assert data["source_kind"] == "unstructured_knowledge"
    assert any(item["title"] == "演示合同变更规范" for item in data["items"])
    assert settings.embedding_dimensions == 384
