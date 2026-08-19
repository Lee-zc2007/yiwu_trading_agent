from backend.app.core.database import SessionLocal
from backend.app.models import Customer
from backend.app.models import Transaction
from backend.app.risk.decision import TransactionDecisionService
from backend.app.risk.evidence import EvidenceCompletenessService
from backend.app.risk.exposure import RiskExposureService
from backend.app.risk.mitigation import RiskMitigationService
from backend.app.risk.scoring import CustomerTrustService
from backend.app.risk.terms import CreditTermsService


def test_customer_trust_does_not_invent_payment_due_dates(client):
    with SessionLocal() as db:
        customer = db.query(Customer).filter(Customer.id == 1, Customer.merchant_id == 1).one()
        trust = CustomerTrustService(db, 1).calculate(customer)
    assert trust["transaction_count"] >= 15
    assert trust["on_time_payment_rate"] is None
    assert trust["payment_timing_assessed_count"] == 0
    assert "payment_due_date" in trust["missing_fields"]


def test_risk_exposure_uses_confirmed_payment_and_never_goes_negative():
    service = RiskExposureService()
    result = service.calculate(
        order_amount=50000,
        currency="USD",
        planned_shipping_value=50000,
        planned_payment_before_shipping=10000,
    )
    assert result["projected_max_exposure"] == 40000

    covered = service.calculate(
        order_amount=50000,
        currency="USD",
        planned_shipping_value=50000,
        mitigations=[{"mitigation_type": "INSURANCE", "verified": True, "coverage_amount": 80000, "currency": "USD"}],
    )
    assert covered["coverage_amount"] == 50000
    assert covered["projected_max_exposure"] == 0


def test_unverified_insurance_cannot_reduce_exposure():
    result = RiskExposureService().calculate(
        order_amount=50000,
        currency="USD",
        planned_shipping_value=50000,
        mitigations=[{"mitigation_type": "INSURANCE", "verified": False, "coverage_amount": 50000, "currency": "USD"}],
    )
    assert result["coverage_amount"] == 0
    assert result["projected_max_exposure"] == 50000


def test_evidence_completeness_ignores_irrelevant_documents():
    result = EvidenceCompletenessService().evaluate(
        context={"amount": 80000, "credit_days": 45, "mitigations": []},
        customer_trust={"transaction_count": 0, "trust_level": "developing"},
        evidence_items=[
            {"evidence_type": "CHAT_RECORD", "verified": True}
            for _ in range(20)
        ],
    )
    assert result["completeness"] == 0
    assert {"IDENTITY", "CONTRACT", "PAYER_IDENTITY", "PAYMENT_TERMS"}.issubset(result["critical_missing"])


def test_credit_terms_are_advisory_and_actionable():
    result = CreditTermsService().evaluate(
        customer_trust={"trust_level": "developing", "confidence_level": "low"},
        transaction_context={"amount": 30000, "deposit_ratio": 0.2, "credit_days": 45, "missing_fields": []},
        transaction_risk={"risk_level": "high"},
        risk_exposure={"projected_max_exposure": 24000},
        evidence={"completeness": 1, "critical_missing": []},
        mitigations={"coverage_amount": 0},
    )
    assert result["status"] == "RECOMMENDED_WITH_ADJUSTMENTS"
    assert result["recommended_min_deposit_ratio"] == 0.5
    assert result["recommended_credit_days"] == 15
    assert result["human_decision_required"] is True


def test_mitigation_reports_real_coverage_without_score():
    result = RiskMitigationService().evaluate(
        mitigations=[
            {"mitigation_type": "GUARANTEE", "verified": True, "coverage_amount": 12000, "currency": "USD"},
            {"mitigation_type": "INSURANCE", "verified": False, "coverage_amount": 10000, "currency": "USD"},
        ],
        currency="USD",
        exposure_base=20000,
    )
    assert result["coverage_amount"] == 12000
    assert result["coverage_ratio"] == 0.6
    assert "mitigation_score" not in result


def test_transaction_decision_uses_new_credit_term_rules(client):
    with SessionLocal() as db:
        result = TransactionDecisionService(db, 1).evaluate(transaction_context={
            "amount": 30000,
            "currency": "USD",
            "deposit_ratio": 0.2,
            "credit_days": 45,
            "final_payment_due_type": "AFTER_DELIVERY",
            "identity_verified": True,
            "contract_signed": True,
            "payer_matches_contract": True,
            "payment_terms_verified": True,
            "mitigations": [],
        })
    rules = {item["rule_code"]: item for item in result["transaction_risk"]["triggered_rules"]}
    assert {"FIRST_CREDIT_EXPOSURE", "LOW_DEPOSIT_RATIO", "LONG_CREDIT_TERM", "DEFERRED_FINAL_PAYMENT"}.issubset(rules)
    assert all({"severity", "reason", "evidence", "risk_contribution"}.issubset(item) for item in rules.values())
    assert result["transaction_risk"]["risk_level"] == "high"
    assert result["risk_exposure"]["projected_max_exposure"] == 24000


def test_isolation_forest_signal_cannot_create_high_or_critical(monkeypatch, client):
    monkeypatch.setattr(
        "backend.app.risk.decision.service.RiskRuleEngine.evaluate",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "backend.app.risk.decision.service.AnomalyService.analyze",
        lambda *args, **kwargs: {
            "anomaly_detected": True,
            "anomaly_score": 0.99,
            "model_version": "test-if",
            "feature_deviations": [{"feature": "order_amount", "value": 99}],
            "explanation": "测试高异常信号",
        },
    )
    with SessionLocal() as db:
        result = TransactionDecisionService(db, 1).evaluate(transaction_context={
            "amount": 30000,
            "currency": "USD",
            "deposit_ratio": 0.5,
            "credit_days": 0,
            "identity_verified": True,
            "contract_signed": True,
            "payer_matches_contract": True,
            "payment_terms_verified": True,
        })
    assert result["anomaly_signal"]["anomaly_score"] == 0.99
    assert result["anomaly_signal"]["signal_role"] == "auxiliary_only"
    assert result["transaction_risk"]["risk_level"] == "low"


def test_simulation_does_not_modify_transaction(client):
    with SessionLocal() as db:
        transaction = db.query(Transaction).filter(Transaction.id == 1, Transaction.merchant_id == 1).one()
        original_deposit = transaction.deposit_ratio
        result = TransactionDecisionService(db, 1).simulate(
            base_context={"deposit_ratio": original_deposit},
            adjustments={"deposit_ratio": 0.6},
            transaction=transaction,
        )
        db.expire(transaction)
        assert transaction.deposit_ratio == original_deposit
    assert result["persisted"] is False
    assert result["comparison"]["deposit_ratio_after"] == 0.6


def test_decision_api_evaluates_and_simulates_draft_without_writes(client):
    context = {
        "amount": 30000,
        "currency": "USD",
        "deposit_ratio": 0.2,
        "credit_days": 45,
        "final_payment_due_type": "AFTER_DELIVERY",
        "identity_verified": True,
        "contract_signed": True,
        "payer_matches_contract": True,
        "payment_terms_verified": True,
    }
    evaluated = client.post("/api/decisions/evaluate", json={"transaction_context": context})
    assert evaluated.status_code == 200
    decision = evaluated.json()["data"]
    assert decision["risk_exposure"]["projected_max_exposure"] == 24000
    assert decision["credit_terms"]["human_decision_required"] is True

    simulated = client.post("/api/decisions/simulate", json={
        "base_context": context,
        "adjustments": {"deposit_ratio": 0.4},
    })
    assert simulated.status_code == 200
    comparison = simulated.json()["data"]["comparison"]
    assert comparison["projected_exposure_change"] == -6000
    assert simulated.json()["data"]["persisted"] is False


def test_transaction_decision_resources_are_merchant_scoped(client):
    terms = client.put("/api/transactions/2/terms", json={
        "credit_days": 30,
        "deposit_ratio": 0.4,
        "deposit_amount": 1500,
        "contract_signed": True,
        "payer_matches_contract": True,
        "planned_shipping_value": 5000,
        "planned_payment_before_shipping": 2000,
    })
    assert terms.status_code == 200
    assert client.get("/api/transactions/2/terms").json()["data"]["credit_days"] == 30

    evidence = client.post("/api/transactions/2/evidence", json={
        "evidence_type": "CONTRACT",
        "verified": True,
        "status": "verified",
        "file_reference": "vault://tradeguard/test-contract",
        "summary": "合同主体和付款条款已人工核验",
    })
    assert evidence.status_code == 201
    mitigation = client.post("/api/transactions/2/mitigations", json={
        "mitigation_type": "GUARANTEE",
        "verified": True,
        "coverage_amount": 1000,
        "currency": "USD",
    })
    assert mitigation.status_code == 201
    assert client.get("/api/transactions/2/exposure").status_code == 200
    assert client.get("/api/transactions/2/decision").status_code == 200
    assert client.get("/api/transactions/2/timeline").status_code == 200

    headers = {"X-Merchant-ID": "999"}
    for path in ["terms", "evidence", "mitigations", "exposure", "decision", "timeline"]:
        assert client.get(f"/api/transactions/2/{path}", headers=headers).status_code == 404


def test_transaction_evidence_package_supports_json_html_and_tenant_isolation(client):
    transaction = client.get("/api/transactions/2").json()["data"]
    generated = client.post("/api/transactions/2/evidence-package")
    assert generated.status_code == 201
    body = generated.json()["data"]
    assert len(body["checksum"]) == 64
    package = body["package_data"]
    assert package["package_version"] == "transaction_evidence_package_v1"
    assert package["customer"]["customer_id"] == transaction["customer_id"]
    assert "email" not in package["customer"]
    assert "phone" not in package["customer"]
    assert "decision" in package
    assert "timeline" in package

    json_response = client.get("/api/transactions/2/evidence-package")
    assert json_response.status_code == 200
    assert json_response.json()["data"]["checksum"] == body["checksum"]

    html_response = client.get("/api/transactions/2/evidence-package?format=html")
    assert html_response.status_code == 200
    assert html_response.headers["content-type"].startswith("text/html")
    assert "TradeGuard AI 交易证据包" in html_response.text
    assert html_response.headers["x-evidence-package-checksum"] == body["checksum"]

    other_merchant = {"X-Merchant-ID": "999"}
    assert client.post("/api/transactions/2/evidence-package", headers=other_merchant).status_code == 404
    assert client.get("/api/transactions/2/evidence-package", headers=other_merchant).status_code == 404
