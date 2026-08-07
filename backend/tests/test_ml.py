from datetime import datetime, timedelta
from types import SimpleNamespace

from backend.app.risk.anomaly.service import AnomalyService
from ml.feature_engineering import FEATURE_NAMES, extract_order_features
from ml.model_registry import model_registry


def test_shared_feature_pipeline_has_expected_shape():
    now = datetime(2026, 8, 7, 10)
    history = [SimpleNamespace(amount=1000, order_time=now - timedelta(days=3), payment_time=now - timedelta(days=2), refund_status="none", dispute_status="none", cancelled=False, payment_method="T/T", product_category="家居", shipping_address="A")]
    order = {"amount": 9000, "order_time": now, "payment_time": None, "deposit_ratio": .1, "payment_method": "OA", "product_category": "机械", "shipping_address": "B"}
    features = extract_order_features(history, order)
    assert list(features) == FEATURE_NAMES
    assert features["amount_to_history_mean"] == 9
    assert features["payment_method_changed"] == 1


def test_model_prediction_and_statistical_fallback_are_bounded(client):
    assert model_registry.status()["status"] == "ready"
    features = {name: 0.0 for name in FEATURE_NAMES}
    features.update(order_amount=10000, amount_to_history_mean=2, customer_history_count=5)
    prediction = model_registry.predict_one(features)
    fallback = AnomalyService.statistical_score(features)
    assert 0 <= prediction["anomaly_score"] <= 1
    assert 0 <= fallback <= 1
