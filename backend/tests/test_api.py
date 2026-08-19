from datetime import datetime

from backend.app.core.database import SessionLocal
from backend.app.models import AgentDecisionContext, Transaction


def test_health_and_seed_counts(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["data"]["status"] == "ok"
    customers = client.get("/api/customers?page_size=100").json()["data"]
    transactions = client.get("/api/transactions?page_size=100").json()["data"]
    alerts = client.get("/api/risk/alerts?page_size=100").json()["data"]
    assert customers["total"] == 20
    assert transactions["total"] == 300
    assert alerts["total"] >= 10


def test_blacklist_score_and_recalculation_are_deterministic(client):
    first = client.get("/api/customers/14/credit-score").json()["data"]
    second = client.post("/api/customers/14/credit-score/recalculate").json()["data"]
    assert first["total_score"] == second["total_score"]
    assert first["total_score"] <= 25
    assert second["risk_level"] == "高风险"


def test_order_risk_creates_traceable_event(client):
    response = client.post(
        "/api/risk/analyze-order",
        json={
            "customer_id": 1,
            "amount": 120000,
            "currency": "USD",
            "product_category": "家居用品",
            "product_name": "大额采购订单",
            "payment_method": "Open Account 90 days",
            "deposit_ratio": 0,
            "shipping_country": "France",
            "shipping_address": "New Warehouse, Paris",
            "order_time": "2026-08-19T10:00:00",
        },
    )
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["risk_event_id"] is not None
    assert result["risk_level"] in {"high", "critical"}
    assert "SMALL_TO_LARGE" in {item["rule_code"] for item in result["triggered_rules"]}
    event = client.get(f"/api/risk/alerts/{result['risk_event_id']}").json()["data"]
    assert event["evidence"]["model_version"] == result["model_version"]


def test_high_risk_action_requires_explicit_confirmation(client):
    event_id = client.get("/api/risk/alerts?page_size=1").json()["data"]["items"][0]["id"]
    payload = {"status": "investigating", "action": "blacklist", "confirmed": False, "resolution": "测试", "assigned_to": "QA"}
    rejected = client.put(f"/api/risk/alerts/{event_id}/status", json=payload)
    assert rejected.status_code == 400
    payload["confirmed"] = True
    accepted = client.put(f"/api/risk/alerts/{event_id}/status", json=payload)
    assert accepted.status_code == 200


def test_csv_import_reports_success_and_row_error(client):
    content = (
        "customer_id,order_number,product_category,product_name,amount,order_time,payment_method,shipping_country,shipping_address\n"
        f"1,PYTEST-{datetime.now().timestamp()},家居用品,测试商品,12000,2026-08-07T10:00:00,T/T 30/70,France,Demo Address\n"
        "999999,PYTEST-BAD,家居用品,测试商品,12000,2026-08-07T10:00:00,T/T 30/70,France,Demo Address\n"
    )
    response = client.post("/api/transactions/import", files={"file": ("test.csv", content.encode("utf-8"), "text/csv")})
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["success_count"] == 1
    assert result["failed_count"] == 1
    assert result["errors"][0]["row"] == 3


def test_deterministic_agent_uses_tools_and_returns_sources(client):
    response = client.post("/api/agent/chat", json={"message": "解释这个客户为什么有风险", "customer_id": 5, "conversation_id": "pytest"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "deterministic"
    assert len(data["tools_called"]) >= 2
    assert data["data_sources"]
    assert data["tools_used"] == ["get_customer_credit_score", "get_customer_transactions", "search_risk_knowledge", "get_order_risk_analysis"]
    assert data["evidence"]
    assert data["related_customer"]["id"] == 5
    assert isinstance(data["related_orders"], list)
    assert isinstance(data["risk_events"], list)
    call_nodes = [item["node"] for item in data["call_chain"]]
    assert call_nodes[:3] == ["START", "Load Context", "Intent Detection"]
    assert "Context Extraction" in call_nodes
    assert "Context Merge" in call_nodes
    assert "Required Fields" in call_nodes
    assert "Tool Selection" in call_nodes
    assert call_nodes.count("Tool Execution") == len(data["tools_used"])
    assert call_nodes[-3:] == ["Evidence Collection", "Response Generation", "END"]
    assert len(data["state_history"]) == len(data["call_chain"])
    assert "仅基于工具返回" in data["disclaimer"]


def test_agent_accepts_empty_string_ids_and_creates_conversation(client):
    response = client.post("/api/agent/chat", json={"message": "最近高风险预警", "customer_id": "", "conversation_id": ""})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "deterministic"
    assert data["conversation_id"]
    conversation = client.get(f"/api/agent/conversations/{data['conversation_id']}")
    assert conversation.status_code == 200
    assert len(conversation.json()["data"]["messages"]) == 2


def test_agent_conversation_management_is_merchant_scoped(client):
    created = client.post("/api/agent/conversations", json={"title": "路演核验会话", "customer_id": 5})
    assert created.status_code == 201
    conversation_id = created.json()["data"]["conversation_id"]
    assert client.get("/api/agent/conversations").status_code == 200
    assert client.get(f"/api/agent/conversations/{conversation_id}", headers={"X-Merchant-ID": "999"}).status_code == 404
    assert client.delete(f"/api/agent/conversations/{conversation_id}").status_code == 200


def test_agent_reads_saved_score_without_recalculation(client):
    before = client.get("/api/customers/5/credit-score/history").json()["data"]
    response = client.post("/api/agent/chat", json={"message": "解释已有信用和风险证据", "customer_id": "5", "conversation_id": "readonly-score"})
    after = client.get("/api/customers/5/credit-score/history").json()["data"]
    assert response.status_code == 200
    assert len(after) == len(before)


def test_merchant_isolation_rejects_cross_merchant_access(client):
    response = client.get("/api/customers/1", headers={"X-Merchant-ID": "999"})
    assert response.status_code == 404


def test_agent_multiturn_decision_context_and_simulation(client):
    conversation_id = "pytest-decision-context"
    with SessionLocal() as db:
        transaction_count_before = db.query(Transaction).count()

    first = client.post("/api/agent/chat", json={
        "message": "一个迪拜客户第一次合作，准备做3万美元订单，希望给45天账期。",
        "conversation_id": conversation_id,
    }).json()["data"]
    assert first["intent"] == "transaction_decision"
    assert first["transaction_context"]["amount"] == 30000
    assert first["transaction_context"]["currency"] == "USD"
    assert first["transaction_context"]["credit_days"] == 45
    assert first["next_best_question"] == "这笔订单客户计划支付多少比例的定金？"
    assert "deposit_ratio" in first["missing_fields"]
    assert first["tools_used"] == []

    second = client.post("/api/agent/chat", json={
        "message": "20%定金，已经核验企业身份，合同也签了。",
        "conversation_id": conversation_id,
    }).json()["data"]
    assert second["transaction_context"]["deposit_ratio"] == 0.2
    assert second["transaction_context"]["identity_verified"] is True
    assert second["transaction_context"]["contract_signed"] is True
    assert second["missing_fields"] == ["payer_matches_contract"]
    assert second["next_best_question"] == "付款主体是否与合同主体一致？"

    third = client.post("/api/agent/chat", json={
        "message": "付款主体与合同主体一致。",
        "conversation_id": conversation_id,
    }).json()["data"]
    assert third["missing_fields"] == []
    assert third["information_completeness"] == 1
    assert third["tools_used"] == ["evaluate_credit_terms"]
    assert third["decision_result"]["risk_exposure"]["projected_max_exposure"] == 24000
    assert third["decision_result"]["transaction_risk"]["risk_level"] == "high"

    fourth = client.post("/api/agent/chat", json={
        "message": "如果定金提高到40%呢？",
        "conversation_id": conversation_id,
    }).json()["data"]
    assert fourth["intent"] == "modify_transaction_terms"
    assert fourth["tools_used"] == ["simulate_transaction_adjustment"]
    assert fourth["transaction_context"]["deposit_ratio"] == 0.4
    assert fourth["comparison"]["deposit_ratio_before"] == 0.2
    assert fourth["comparison"]["deposit_ratio_after"] == 0.4
    assert fourth["comparison"]["projected_exposure_change"] == -6000

    with SessionLocal() as db:
        assert db.query(Transaction).count() == transaction_count_before
        context = db.query(AgentDecisionContext).filter(
            AgentDecisionContext.merchant_id == 1,
            AgentDecisionContext.conversation_id == conversation_id,
        ).one()
        assert context.transaction_context["deposit_ratio"] == 0.4


def test_agent_answers_risk_methodology_from_deterministic_tool(client):
    response = client.post("/api/agent/chat", json={
        "message": "这个系统对于客户风险的评价标准是什么？",
        "conversation_id": "pytest-risk-methodology",
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["intent"] == "risk_methodology"
    assert data["tools_used"] == ["get_risk_evaluation_criteria"]
    assert "Customer Trust" in data["answer"]
    assert "Risk Exposure" in data["answer"]
    assert any(item["source_type"] == "risk_methodology" for item in data["evidence"])
