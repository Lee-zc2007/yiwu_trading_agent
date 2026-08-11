from datetime import datetime


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


def test_demo_risk_creates_traceable_event(client):
    response = client.post("/api/risk/demo-scenarios/small_to_large/run")
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


def test_mock_agent_uses_tools_and_returns_sources(client):
    response = client.post("/api/agent/chat", json={"message": "解释这个客户为什么有风险", "customer_id": 5, "conversation_id": "pytest"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "mock"
    assert len(data["tools_called"]) >= 2
    assert data["data_sources"]
    assert data["tools_used"] == ["get_customer_credit_score", "get_customer_transactions", "search_risk_knowledge", "get_order_risk_analysis"]
    assert data["evidence"]
    assert data["related_customer"]["id"] == 5
    assert isinstance(data["related_orders"], list)
    assert isinstance(data["risk_events"], list)
    assert [item["node"] for item in data["call_chain"]] == [
        "START",
        "Intent Detection",
        "Tool Selection",
        "Tool Execution",
        "Tool Execution",
        "Evidence Collection",
        "Response Generation",
        "END",
    ]
    assert len(data["state_history"]) == len(data["call_chain"])
    assert "仅基于工具返回" in data["disclaimer"]


def test_agent_accepts_empty_string_ids_and_creates_conversation(client):
    response = client.post("/api/agent/chat", json={"message": "最近高风险预警", "customer_id": "", "conversation_id": ""})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "mock"
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
