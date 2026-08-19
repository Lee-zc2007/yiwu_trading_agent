from sqlalchemy.orm import Session

from ..models import Customer, RiskEvent, Transaction
from .anomaly import AnomalyService
from .explanations import build_recommendations
from .rules import RiskRuleEngine
from .scoring import CreditScoringService


DISCLAIMER = "风险评分、规则与模型结果仅供辅助判断，最终决策应由商户结合实际情况作出。"


def overall_level(score: float) -> str:
    if score >= 80: return "critical"
    if score >= 60: return "high"
    if score >= 35: return "medium"
    return "low"


class RiskAssessmentService:
    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id

    def analyze_order(self, customer: Customer, order: dict, order_id: int | None = None, persist_event: bool = True) -> dict:
        history_query = self.db.query(Transaction).filter(Transaction.merchant_id == self.merchant_id, Transaction.customer_id == customer.id)
        if order_id:
            history_query = history_query.filter(Transaction.id != order_id)
        history = history_query.order_by(Transaction.order_time).all()
        credit, _ = CreditScoringService(self.db, self.merchant_id).latest_or_calculate(customer)
        triggered = RiskRuleEngine(self.db, self.merchant_id).evaluate(customer, order, history)
        anomaly = AnomalyService(self.db, self.merchant_id).analyze(history, order)
        rule_score = max([item["risk_score"] for item in triggered], default=0)
        rule_contribution = sum(item.get("risk_contribution", 0) for item in triggered)
        historical_events = self.db.query(RiskEvent).filter(RiskEvent.merchant_id == self.merchant_id, RiskEvent.customer_id == customer.id, RiskEvent.status.in_(["pending", "investigating", "confirmed"])).count()
        credit_risk = 100 - credit.total_score
        # 综合交易风险由确定性规则主导。客户历史与未结事件只作有限修正；
        # Isolation Forest 明确不参与固定加权，不能单独把交易升级为 HIGH/CRITICAL。
        if triggered:
            supplementary = max(0, rule_contribution - max(item.get("risk_contribution", 0) for item in triggered))
            overall = min(100.0, rule_score + min(8, supplementary * 0.1) + min(6, historical_events * 1.5))
        else:
            overall = min(30.0, credit_risk * 0.12 + min(6, historical_events * 1.5))
        level = overall_level(overall)
        main_reasons = [item["reason"] for item in triggered[:4]]
        if anomaly["anomaly_detected"]:
            main_reasons.append(f"辅助行为异常信号为 {anomaly['anomaly_score']:.0%}，需核验但不单独决定风险等级")
        if credit.total_score < 60:
            main_reasons.append(f"客户当前信用分仅 {credit.total_score:.1f}")
        if not main_reasons:
            main_reasons.append("未发现显著行为突变，继续保持常规监控")
        recommendations = build_recommendations(level, triggered)
        event = None
        if persist_event and (overall >= 35 or triggered):
            event = RiskEvent(
                merchant_id=self.merchant_id,
                customer_id=customer.id,
                order_id=order_id,
                risk_type=triggered[0]["rule_code"] if triggered else "ANOMALY_DETECTION",
                risk_level=level,
                risk_score=round(overall, 2),
                title=f"{customer.company_name} 新订单风险预警",
                description="；".join(main_reasons),
                triggered_rules=triggered,
                evidence={
                    "features": anomaly["features"],
                    "statistical_anomaly_score": anomaly["statistical_anomaly_score"],
                    "anomaly_score": anomaly["anomaly_score"],
                    "anomaly_detected": anomaly["anomaly_detected"],
                    "feature_deviations": anomaly["feature_deviations"],
                    "anomaly_explanation": anomaly["explanation"],
                    "model_version": anomaly["model_version"],
                    "model_status": anomaly["model_status"],
                    "rule_version": RiskRuleEngine.version,
                    "credit_rule_version": credit.rule_version,
                    "recommendations": recommendations,
                },
            )
            self.db.add(event)
            self.db.flush()
        return {
            "customer_id": customer.id,
            "order_id": order_id,
            "risk_event_id": event.id if event else None,
            "credit_score": credit.total_score,
            "credit_confidence": credit.confidence_level,
            "overall_risk_score": round(overall, 2),
            "risk_level": level,
            "statistical_anomaly_score": anomaly["statistical_anomaly_score"],
            "anomaly_score": anomaly["anomaly_score"],
            "anomaly_signal": {
                "anomaly_detected": anomaly["anomaly_detected"],
                "anomaly_score": anomaly["anomaly_score"],
                "model_version": anomaly["model_version"],
                "feature_deviations": anomaly["feature_deviations"],
                "explanation": anomaly["explanation"],
                "signal_role": "auxiliary_only",
            },
            "triggered_rules": triggered,
            "main_reasons": main_reasons,
            "recommendations": recommendations,
            "model_version": anomaly["model_version"],
            "model_status": anomaly["model_status"],
            "rule_version": RiskRuleEngine.version,
            "disclaimer": DISCLAIMER,
            "feature_snapshot": anomaly["features"],
        }
