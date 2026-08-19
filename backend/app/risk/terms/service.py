from __future__ import annotations


class CreditTermsService:
    """把确定性风险结果转为可执行交易条件建议，最终决策仍由商户作出。"""

    statuses = {
        "RECOMMENDED",
        "RECOMMENDED_WITH_ADJUSTMENTS",
        "REQUIRES_REVIEW",
        "INSUFFICIENT_INFORMATION",
    }

    def evaluate(
        self,
        *,
        customer_trust: dict,
        transaction_context: dict,
        transaction_risk: dict,
        risk_exposure: dict,
        evidence: dict,
        mitigations: dict,
    ) -> dict:
        amount = float(transaction_context.get("amount") or 0)
        current_deposit = float(transaction_context.get("deposit_ratio") or 0)
        current_days = int(transaction_context.get("credit_days") or 0)
        risk_level = str(transaction_risk.get("risk_level", "unknown")).lower()
        trust_level = str(customer_trust.get("trust_level", "developing")).lower()
        critical_missing = list(evidence.get("critical_missing", []))
        missing_information = list(transaction_context.get("missing_fields", []))

        if missing_information or critical_missing or amount <= 0:
            status = "INSUFFICIENT_INFORMATION"
        elif risk_level == "critical" or trust_level == "low" or customer_trust.get("blacklist_status"):
            status = "REQUIRES_REVIEW"
        elif (
            risk_level in {"high", "medium"}
            or trust_level == "developing"
            or evidence.get("completeness", 0) < 1
            or current_days > 30
            or current_deposit < 0.3
        ):
            status = "RECOMMENDED_WITH_ADJUSTMENTS"
        else:
            status = "RECOMMENDED"

        minimum_deposit = 0.2
        if trust_level == "developing" or risk_level in {"high", "critical"}:
            minimum_deposit = 0.5
        elif risk_level == "medium" or customer_trust.get("confidence_level") == "low":
            minimum_deposit = 0.3
        if risk_level == "critical":
            minimum_deposit = 0.7
        recommended_deposit = max(current_deposit, minimum_deposit)

        if trust_level == "developing":
            recommended_days = min(current_days or 15, 15)
        elif risk_level in {"high", "critical"}:
            recommended_days = min(current_days or 15, 15)
        elif risk_level == "medium":
            recommended_days = min(current_days or 30, 30)
        else:
            recommended_days = min(current_days or 45, 45)

        suggested_max_exposure = max(
            0.0,
            amount * (1 - recommended_deposit) - float(mitigations.get("coverage_amount", 0) or 0),
        )
        recommendations: list[str] = []
        if recommended_deposit > current_deposit:
            recommendations.append(f"最低定金比例建议提高至 {recommended_deposit:.0%}")
        if current_days > recommended_days:
            recommendations.append(f"账期建议缩短至不超过 {recommended_days} 天")
        if trust_level == "developing":
            recommendations.extend(["先进行小额试单", "采用分批付款和分批发货"])
        if critical_missing:
            recommendations.append("补齐关键证据：" + "、".join(critical_missing))
        if risk_exposure.get("projected_max_exposure", 0) > suggested_max_exposure:
            recommendations.append("发货前增加已确认收款或已核验保障，降低未保障敞口")

        return {
            "status": status,
            "credit_recommended": status in {"RECOMMENDED", "RECOMMENDED_WITH_ADJUSTMENTS"},
            "recommended_credit_days": recommended_days,
            "recommended_max_exposure": round(suggested_max_exposure, 2),
            "recommended_min_deposit_ratio": round(recommended_deposit, 4),
            "recommended_payment_milestones": [
                f"签约后支付至少 {recommended_deposit:.0%} 定金",
                "发货前确认约定付款节点到账",
                f"尾款账期不超过 {recommended_days} 天",
            ],
            "partial_payment_recommended": status != "RECOMMENDED" or trust_level == "developing",
            "partial_shipment_recommended": status != "RECOMMENDED" or trust_level == "developing",
            "required_evidence": critical_missing,
            "recommendations": recommendations,
            "human_decision_required": True,
        }
