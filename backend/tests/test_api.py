from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402


def test_health_and_seed_data():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert response.json()["products"] >= 5


def test_dashboard_has_demo_notice():
    with TestClient(app) as client:
        payload = client.get("/api/dashboard").json()
        assert len(payload["metrics"]) == 10
        assert "Demo" in payload["disclaimer"]


def test_quote_calculation_and_pdf():
    request = {"product_id": 1, "quantity": 1000, "unit_price": 12.8, "unit_cost": 7.6, "discount": 2, "packaging_fee": 100, "freight": 500, "insurance": 40, "tax_rate": 2, "incoterm": "FOB"}
    with TestClient(app) as client:
        result = client.post("/api/quotes/calculate", json=request)
        assert result.status_code == 200
        assert result.json()["total_amount"] > result.json()["total_cost"]
        pdf = client.post("/api/quotes/preview/pdf", json=request)
        assert pdf.status_code == 200
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")


def test_explainable_risk_model():
    payload = {"registered_years": 0, "profile_completeness": 20, "historical_orders": 0, "historical_amount": 0, "disputes": 2, "payment_method": "货到付款 COD", "order_amount": 180000, "address_complete": False, "corporate_email": False, "account_changes": 3, "verification_refused": True, "urgent_language": True, "behavior_consistent": False}
    with TestClient(app) as client:
        result = client.post("/api/risk/evaluate", json=payload)
        assert result.status_code == 200
        body = result.json()
        assert body["score"] >= 80
        assert body["level"] == "极高风险"
        assert len(body["factors"]) >= 12


def test_contract_review_detects_risks():
    text = "买方要求货到付款，卖方承担全部责任，并可随时变更收款账户。交付时间另行通知。"
    with TestClient(app) as client:
        result = client.post("/api/contracts/analyze", json={"text": text})
        assert result.status_code == 200
        assert result.json()["risk_level"] == "高风险"
        assert len(result.json()["issues"]) >= 4


def test_impact_calculation():
    with TestClient(app) as client:
        result = client.post("/api/analytics/impact", json={})
        assert result.status_code == 200
        assert result.json()["saved_hours_day"] > 0

