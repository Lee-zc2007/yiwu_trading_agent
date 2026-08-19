from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy.orm import Session

from ...models import (
    Customer,
    Transaction,
    TransactionDecisionSnapshot,
    TransactionEvidenceItem,
    TransactionMitigation,
)
from ..anomaly import AnomalyService
from ..evidence import EvidenceCompletenessService
from ..exposure import RiskExposureService
from ..mitigation import RiskMitigationService
from ..rules import RiskRuleEngine
from ..scoring import CustomerTrustService
from ..terms import CreditTermsService


SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
SEVERITY_SCORE_CAP = {"low": 34, "medium": 59, "high": 79, "critical": 100}


class TransactionDecisionService:
    """统一编排确定性交易决策能力。

    LLM 和 Agent 只能通过受控 Tool 调用本服务；所有规则、敞口、证据和授信条件
    都在此处或下游确定性 Service 中计算。
    """

    version = "transaction_decision_v1"

    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id

    def _transaction_context(self, transaction: Transaction) -> dict:
        terms = transaction.terms
        mitigations = [
            {
                "mitigation_type": item.mitigation_type,
                "verified": item.verified,
                "coverage_amount": item.coverage_amount,
                "currency": item.currency,
                "description": item.description,
            }
            for item in transaction.mitigations
        ]
        return {
            "amount": transaction.amount,
            "currency": transaction.currency,
            "deposit_ratio": terms.deposit_ratio if terms and terms.deposit_ratio is not None else transaction.deposit_ratio,
            "deposit_amount": terms.deposit_amount if terms else None,
            "credit_days": terms.credit_days if terms else None,
            "final_payment_ratio": terms.final_payment_ratio if terms else None,
            "final_payment_due_type": terms.final_payment_due_type if terms else None,
            "contract_signed": terms.contract_signed if terms else None,
            "payer_matches_contract": terms.payer_matches_contract if terms else None,
            "payment_account_changed": terms.payment_account_changed if terms else None,
            "payment_account_verified": terms.payment_account_verified if terms else None,
            "planned_shipping_value": terms.planned_shipping_value if terms else transaction.amount,
            "planned_payment_before_shipping": terms.planned_payment_before_shipping if terms else None,
            "product_category": transaction.product_category,
            "product_name": transaction.product_name,
            "payment_method": transaction.payment_method,
            "shipping_country": transaction.shipping_country,
            "shipping_address": transaction.shipping_address,
            "order_time": transaction.order_time,
            "payment_time": transaction.payment_time,
            "mitigations": mitigations,
        }

    def _customer_trust(self, customer: Customer | None, context: dict) -> dict:
        if customer is None:
            return {
                "customer_id": None,
                "transaction_count": 0,
                "cooperation_days": 0,
                "total_amount": 0,
                "max_order_amount": 0,
                "on_time_payment_rate": None,
                "overdue_count": 0,
                "average_overdue_days": None,
                "refund_rate": None,
                "dispute_rate": None,
                "rejection_count": 0,
                "identity_verified": context.get("identity_verified") is True,
                "trust_level": "developing",
                "confidence_level": "low",
                "missing_fields": ["transaction_history"],
                "calculation_version": "customer_trust_v2",
                "reason": "首次合作或尚未关联客户档案，历史履约数据不足",
                "blacklist_status": False,
            }
        result = CustomerTrustService(self.db, self.merchant_id).calculate(customer, save=False)
        result["blacklist_status"] = customer.blacklist_status
        return result

    def _customer_for_rules(self, customer: Customer | None, context: dict):
        if customer is not None:
            return customer
        return SimpleNamespace(
            id=None,
            company_name=context.get("customer_name") or "未建档客户",
            profile_updated_at=None,
            identity_verified=context.get("identity_verified") is True,
            blacklist_status=False,
        )

    def _order_for_rules(self, context: dict, customer: Customer | None) -> dict:
        return {
            **context,
            "amount": float(context.get("amount") or 0),
            "currency": str(context.get("currency") or "USD").upper(),
            "order_time": context.get("order_time") or datetime.now(UTC).replace(tzinfo=None),
            "payment_time": context.get("payment_time"),
            "product_category": context.get("product_category") or (customer.main_product_category if customer else "未指定"),
            "product_name": context.get("product_name") or "拟议交易",
            "payment_method": context.get("payment_method") or ("Open Account" if context.get("credit_days") else "待确认"),
            "shipping_country": context.get("shipping_country") or (customer.country if customer else "待确认"),
            "shipping_address": context.get("shipping_address") or "待确认",
            "deposit_ratio": float(context.get("deposit_ratio") or 0),
        }

    def _transaction_risk(self, customer: Customer | None, transaction: Transaction | None, context: dict) -> tuple[dict, dict]:
        if customer is not None:
            query = self.db.query(Transaction).filter(
                Transaction.merchant_id == self.merchant_id,
                Transaction.customer_id == customer.id,
            )
            if transaction is not None:
                query = query.filter(Transaction.id != transaction.id)
            history = query.order_by(Transaction.order_time).all()
        else:
            history = []
        order = self._order_for_rules(context, customer)
        triggered = RiskRuleEngine(self.db, self.merchant_id).evaluate(self._customer_for_rules(customer, context), order, history)
        anomaly = AnomalyService(self.db, self.merchant_id).analyze(history, order)
        if triggered:
            highest = max((item.get("severity", item["risk_level"]) for item in triggered), key=lambda level: SEVERITY_ORDER.get(level, 1))
            base_score = max(item["risk_score"] for item in triggered)
            extra = max(0, sum(item.get("risk_contribution", 0) for item in triggered) - max(item.get("risk_contribution", 0) for item in triggered))
            score = min(SEVERITY_SCORE_CAP[highest], base_score + min(6, extra * 0.08))
        else:
            highest, score = "low", 10.0
        result = {
            "risk_level": highest,
            "risk_score": round(score, 2),
            "triggered_rules": triggered,
            "main_reasons": [item["reason"] for item in triggered[:5]] or ["确定性规则未发现显著交易条件异常"],
            "rule_version": RiskRuleEngine.version,
        }
        anomaly_signal = {
            "anomaly_detected": anomaly["anomaly_detected"],
            "anomaly_score": anomaly["anomaly_score"],
            "model_version": anomaly["model_version"],
            "feature_deviations": anomaly["feature_deviations"],
            "explanation": anomaly["explanation"],
            "signal_role": "auxiliary_only",
        }
        return result, anomaly_signal

    def evaluate(
        self,
        *,
        transaction_context: dict | None = None,
        customer: Customer | None = None,
        transaction: Transaction | None = None,
        persist_snapshot: bool = False,
    ) -> dict:
        if transaction is not None:
            if transaction.merchant_id != self.merchant_id:
                raise ValueError("交易不属于当前商户")
            if customer is None:
                customer = transaction.customer
            context = {**self._transaction_context(transaction), **(transaction_context or {})}
        else:
            context = dict(transaction_context or {})
        if customer is not None and customer.merchant_id != self.merchant_id:
            raise ValueError("客户不属于当前商户")

        context.setdefault("currency", "USD")
        context.setdefault("mitigations", [])
        if customer is not None:
            context.setdefault("identity_verified", customer.identity_verified)
        trust = self._customer_trust(customer, context)
        transaction_risk, anomaly_signal = self._transaction_risk(customer, transaction, context)

        mitigation_rows = context.get("mitigations", [])
        if transaction is not None and not mitigation_rows:
            mitigation_rows = self.db.query(TransactionMitigation).filter(
                TransactionMitigation.merchant_id == self.merchant_id,
                TransactionMitigation.transaction_id == transaction.id,
            ).all()
        amount = float(context.get("amount") or 0)
        deposit_amount = context.get("deposit_amount")
        if deposit_amount is None:
            deposit_amount = amount * float(context.get("deposit_ratio") or 0)
        planned_payment = context.get("planned_payment_before_shipping")
        if planned_payment is None:
            planned_payment = deposit_amount
        exposure_base = max(0.0, float(context.get("planned_shipping_value") or amount) - float(planned_payment or 0))
        mitigations = RiskMitigationService().evaluate(
            mitigations=mitigation_rows,
            currency=str(context["currency"]),
            exposure_base=exposure_base,
        )
        exposure = RiskExposureService().calculate(
            order_amount=amount,
            currency=str(context["currency"]),
            confirmed_payment_amount=float(context.get("confirmed_payment_amount") or 0),
            shipped_value=float(context.get("shipped_value") or 0),
            delivered_value=float(context.get("delivered_value") or 0),
            planned_shipping_value=float(context.get("planned_shipping_value") or amount),
            planned_payment_before_shipping=float(planned_payment or 0),
            mitigations=mitigation_rows,
        )

        evidence_rows = context.get("evidence_items", [])
        if transaction is not None and not evidence_rows:
            evidence_rows = self.db.query(TransactionEvidenceItem).filter(
                TransactionEvidenceItem.merchant_id == self.merchant_id,
                TransactionEvidenceItem.transaction_id == transaction.id,
            ).all()
        evidence = EvidenceCompletenessService().evaluate(
            context=context,
            evidence_items=evidence_rows,
            customer_trust=trust,
        )
        context_for_terms = {**context, "amount": amount}
        credit_terms = CreditTermsService().evaluate(
            customer_trust=trust,
            transaction_context=context_for_terms,
            transaction_risk=transaction_risk,
            risk_exposure=exposure,
            evidence=evidence,
            mitigations=mitigations,
        )
        main_risks = list(transaction_risk["main_reasons"])
        if evidence["critical_missing"]:
            main_risks.append("关键证据缺失：" + "、".join(evidence["critical_missing"]))
        result = {
            "customer_trust": trust,
            "transaction_risk": transaction_risk,
            "risk_exposure": exposure,
            "evidence": evidence,
            "mitigations": mitigations,
            "anomaly_signal": anomaly_signal,
            "credit_terms": credit_terms,
            "decision_status": credit_terms["status"],
            "main_risks": main_risks,
            "missing_information": sorted(set(context.get("missing_fields", []) + evidence["missing"])),
            "recommendations": credit_terms["recommendations"],
            "calculation_version": self.version,
            "disclaimer": "系统提供确定性风险证据和交易条件建议，最终决策必须由商户人工作出。",
        }
        if persist_snapshot:
            snapshot = TransactionDecisionSnapshot(
                merchant_id=self.merchant_id,
                customer_id=customer.id if customer else None,
                transaction_id=transaction.id if transaction else None,
                decision_status=result["decision_status"],
                decision_data=result,
                calculation_version=self.version,
            )
            self.db.add(snapshot)
            self.db.flush()
            result["decision_snapshot_id"] = snapshot.id
        return result

    def simulate(
        self,
        *,
        base_context: dict,
        adjustments: dict,
        customer: Customer | None = None,
        transaction: Transaction | None = None,
    ) -> dict:
        """只在内存中合并条件并重算，不修改正式交易或条款。"""

        before = self.evaluate(transaction_context=base_context, customer=customer, transaction=transaction, persist_snapshot=False)
        simulated_context = {**base_context, **adjustments}
        after = self.evaluate(transaction_context=simulated_context, customer=customer, transaction=transaction, persist_snapshot=False)
        return {
            "adjustments": adjustments,
            "before": before,
            "after": after,
            "comparison": {
                "projected_exposure_change": round(
                    after["risk_exposure"]["projected_max_exposure"] - before["risk_exposure"]["projected_max_exposure"], 2
                ),
                "deposit_ratio_before": base_context.get("deposit_ratio"),
                "deposit_ratio_after": simulated_context.get("deposit_ratio"),
                "credit_days_before": base_context.get("credit_days"),
                "credit_days_after": simulated_context.get("credit_days"),
                "decision_status_before": before["decision_status"],
                "decision_status_after": after["decision_status"],
            },
            "persisted": False,
        }
