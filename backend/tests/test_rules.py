from datetime import datetime, timedelta
from types import SimpleNamespace

from backend.app.risk.rules.builtin import AmountSurgeRule, SmallToLargeRule


def transaction(amount: float, days_ago: int):
    return SimpleNamespace(amount=amount, order_time=datetime(2026, 8, 7) - timedelta(days=days_ago))


def test_amount_surge_rule_exposes_reproducible_evidence():
    history = [transaction(1000, 3), transaction(1100, 2), transaction(900, 1)]
    result = AmountSurgeRule({"multiple": 5}, "high").evaluate(SimpleNamespace(), {"amount": 7000}, history)
    assert result["triggered"] is True
    assert result["evidence"]["historical_average"] == 1000
    assert result["evidence"]["multiple"] == 7


def test_small_to_large_requires_five_small_orders():
    history = [transaction(value, index) for index, value in enumerate([900, 1100, 1000, 1200, 800], start=1)]
    rule = SmallToLargeRule({"small_limit": 2000, "large_multiple": 5}, "critical")
    assert rule.evaluate(SimpleNamespace(), {"amount": 8000}, history)["rule_code"] == "SMALL_TO_LARGE"
    assert rule.evaluate(SimpleNamespace(), {"amount": 2000}, history) is None
