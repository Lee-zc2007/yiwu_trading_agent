from sqlalchemy.orm import Session

from ml.feature_engineering import extract_order_features
from ml.model_registry import model_registry

from ...models import Transaction


class AnomalyService:
    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id

    @staticmethod
    def statistical_score(features: dict[str, float]) -> float:
        """模型不可用时仍能依据可解释统计量给出 0-1 异常度。"""
        z_component = min(1.0, max(0.0, abs(features["amount_zscore"]) / 5))
        ratio_component = min(1.0, max(0.0, (features["amount_to_history_mean"] - 1) / 7))
        change_component = min(1.0, (features["payment_method_changed"] + features["category_changed"]) / 2)
        adverse_component = min(1.0, features["historical_refund_rate"] + features["historical_dispute_rate"] + features["historical_cancel_rate"])
        return round(0.4 * z_component + 0.3 * ratio_component + 0.15 * change_component + 0.15 * adverse_component, 4)

    def _training_rows(self) -> list[dict[str, float]]:
        rows: list[dict[str, float]] = []
        customer_ids = [row[0] for row in self.db.query(Transaction.customer_id).filter(Transaction.merchant_id == self.merchant_id).distinct().all()]
        for customer_id in customer_ids:
            transactions = (
                self.db.query(Transaction)
                .filter(Transaction.merchant_id == self.merchant_id, Transaction.customer_id == customer_id)
                .order_by(Transaction.order_time)
                .all()
            )
            for index, transaction in enumerate(transactions):
                rows.append(extract_order_features(transactions[:index], transaction))
        return rows

    def analyze(self, history: list[Transaction], order: dict) -> dict:
        features = extract_order_features(history, order)
        statistical = self.statistical_score(features)
        try:
            if model_registry.load() is None:
                rows = self._training_rows()
                if len(rows) >= 30:
                    model_registry.train(rows)
            model_result = model_registry.predict_one(features)
        except Exception as exc:
            model_result = {"anomaly_score": statistical, "raw_score": statistical, "model_version": "statistical_fallback_v1", "model_status": f"fallback:{type(exc).__name__}"}
        anomaly_score = float(model_result.get("anomaly_score", statistical))
        deviations = [
            {"feature": name, "value": round(float(features[name]), 4)}
            for name in [
                "amount_to_history_mean",
                "amount_zscore",
                "payment_method_changed",
                "category_changed",
            ]
            if abs(float(features.get(name, 0))) >= (1.5 if name == "amount_to_history_mean" else 1)
        ]
        detected = anomaly_score >= 0.7
        return {
            "features": features,
            "statistical_anomaly_score": statistical,
            **model_result,
            "anomaly_detected": detected,
            "anomaly_score": anomaly_score,
            "feature_deviations": deviations,
            "explanation": "行为模式明显偏离历史，需要进一步核验" if detected else "未发现足以单独升级风险等级的行为异常信号",
            "signal_role": "auxiliary_only",
        }
