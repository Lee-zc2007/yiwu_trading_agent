from collections import Counter
from datetime import timedelta
from statistics import mean, pstdev


FEATURE_NAMES = [
    "order_amount",
    "amount_to_history_mean",
    "amount_zscore",
    "orders_last_7d",
    "amount_last_30d",
    "payment_delay_days",
    "deposit_ratio",
    "historical_refund_rate",
    "historical_dispute_rate",
    "historical_cancel_rate",
    "address_change_count_30d",
    "payment_method_changed",
    "category_changed",
    "customer_history_count",
]


def _value(item, name, default=None):
    return item.get(name, default) if isinstance(item, dict) else getattr(item, name, default)


def extract_order_features(history: list, order) -> dict[str, float]:
    """训练和推理共享同一特征函数，防止线上线下口径漂移。"""
    order_time = _value(order, "order_time")
    amount = float(_value(order, "amount", 0))
    amounts = [float(_value(tx, "amount", 0)) for tx in history]
    historical_mean = mean(amounts) if amounts else amount
    deviation = pstdev(amounts) if len(amounts) >= 2 else max(historical_mean * 0.25, 1)
    last_7d = [tx for tx in history if _value(tx, "order_time") >= order_time - timedelta(days=7)]
    last_30d = [tx for tx in history if _value(tx, "order_time") >= order_time - timedelta(days=30)]
    refund_rate = sum(_value(tx, "refund_status", "none") != "none" for tx in history) / len(history) if history else 0
    dispute_rate = sum(_value(tx, "dispute_status", "none") != "none" for tx in history) / len(history) if history else 0
    cancel_rate = sum(bool(_value(tx, "cancelled", False)) for tx in history) / len(history) if history else 0
    common_payment = Counter(_value(tx, "payment_method", "") for tx in history).most_common(1)[0][0] if history else _value(order, "payment_method", "")
    common_category = Counter(_value(tx, "product_category", "") for tx in history).most_common(1)[0][0] if history else _value(order, "product_category", "")
    payment_time = _value(order, "payment_time")
    payment_delay = max(0, (payment_time - order_time).days) if payment_time else 0
    return {
        "order_amount": amount,
        "amount_to_history_mean": amount / max(historical_mean, 1),
        "amount_zscore": (amount - historical_mean) / max(deviation, 1),
        "orders_last_7d": float(len(last_7d) + 1),
        "amount_last_30d": float(sum(_value(tx, "amount", 0) for tx in last_30d) + amount),
        "payment_delay_days": float(payment_delay),
        "deposit_ratio": float(_value(order, "deposit_ratio", 0.3)),
        "historical_refund_rate": refund_rate,
        "historical_dispute_rate": dispute_rate,
        "historical_cancel_rate": cancel_rate,
        "address_change_count_30d": float(len({_value(tx, "shipping_address", "") for tx in last_30d} | {_value(order, "shipping_address", "")})),
        "payment_method_changed": float(bool(history) and _value(order, "payment_method", "") != common_payment),
        "category_changed": float(bool(history) and _value(order, "product_category", "") != common_category),
        "customer_history_count": float(len(history)),
    }
