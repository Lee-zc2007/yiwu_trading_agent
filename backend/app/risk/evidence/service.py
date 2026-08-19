from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from ...models import Transaction, TransactionEvidenceItem


class EvidenceCompletenessService:
    """按交易条件生成必需证据清单，并只统计已核验的必需证据。"""

    weights = {
        "IDENTITY": 2.0,
        "CONTRACT": 2.0,
        "PAYER_IDENTITY": 2.0,
        "PAYMENT_TERMS": 1.5,
        "PAYMENT": 1.0,
        "SHIPPING": 1.0,
        "INSPECTION": 1.0,
        "INSURANCE_POLICY": 1.5,
        "LETTER_OF_CREDIT": 1.5,
        "PLATFORM_GUARANTEE": 1.5,
    }
    critical_types = {"IDENTITY", "CONTRACT", "PAYER_IDENTITY", "PAYMENT_TERMS"}

    def __init__(self, db: Session | None = None, merchant_id: int | None = None):
        self.db = db
        self.merchant_id = merchant_id

    @staticmethod
    def _value(item: object | dict, key: str, default=None):
        return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)

    def required_evidence(self, context: dict, customer_trust: dict | None = None) -> list[dict]:
        trust = customer_trust or {}
        first_or_limited = trust.get("transaction_count", 0) < 3 or trust.get("trust_level") == "developing"
        credit_days = int(context.get("credit_days") or 0)
        amount = float(context.get("amount") or 0)
        required = {"IDENTITY", "CONTRACT"}
        if first_or_limited or credit_days > 0:
            required.update({"PAYER_IDENTITY", "PAYMENT_TERMS"})
        if amount >= 50000:
            required.update({"INSPECTION", "SHIPPING"})
        mitigation_types = {
            str(self._value(item, "mitigation_type", "")).upper()
            for item in context.get("mitigations", [])
        }
        if "INSURANCE" in mitigation_types:
            required.add("INSURANCE_POLICY")
        if "LETTER_OF_CREDIT" in mitigation_types:
            required.add("LETTER_OF_CREDIT")
        if "PLATFORM_PROTECTION" in mitigation_types:
            required.add("PLATFORM_GUARANTEE")
        return [
            {"evidence_type": item, "weight": self.weights.get(item, 1.0), "critical": item in self.critical_types}
            for item in sorted(required)
        ]

    def evaluate(
        self,
        *,
        context: dict,
        evidence_items: Iterable[object | dict] = (),
        customer_trust: dict | None = None,
    ) -> dict:
        required = self.required_evidence(context, customer_trust)
        verified_types = {
            str(self._value(item, "evidence_type", "")).upper()
            for item in evidence_items
            if bool(self._value(item, "verified", False))
        }
        # 已在结构化业务字段中核验的事实，同样可以满足对应证据要求。
        if context.get("identity_verified") is True:
            verified_types.add("IDENTITY")
        if context.get("contract_signed") is True:
            verified_types.add("CONTRACT")
        if context.get("payer_matches_contract") is True:
            verified_types.add("PAYER_IDENTITY")
        if context.get("payment_terms_verified") is True:
            verified_types.add("PAYMENT_TERMS")

        required_types = [item["evidence_type"] for item in required]
        verified = [item for item in required_types if item in verified_types]
        missing = [item for item in required_types if item not in verified_types]
        critical_missing = [item["evidence_type"] for item in required if item["critical"] and item["evidence_type"] in missing]
        total_weight = sum(item["weight"] for item in required)
        verified_weight = sum(item["weight"] for item in required if item["evidence_type"] in verified_types)
        return {
            "completeness": round(verified_weight / total_weight, 4) if total_weight else 1.0,
            "verified_weight": verified_weight,
            "required_weight": total_weight,
            "required": required,
            "verified": verified,
            "missing": missing,
            "critical_missing": critical_missing,
            "calculation": "已核验必需证据权重 / 全部必需证据权重",
        }

    def for_transaction(self, transaction: Transaction, customer_trust: dict | None = None) -> dict:
        if self.db is None or self.merchant_id is None:
            raise RuntimeError("按交易检查证据需要数据库会话和 merchant_id")
        if transaction.merchant_id != self.merchant_id:
            raise ValueError("交易不属于当前商户")
        terms = transaction.terms
        items = self.db.query(TransactionEvidenceItem).filter(
            TransactionEvidenceItem.merchant_id == self.merchant_id,
            TransactionEvidenceItem.transaction_id == transaction.id,
        ).all()
        context = {
            "amount": transaction.amount,
            "credit_days": terms.credit_days if terms else None,
            "final_payment_due_type": terms.final_payment_due_type if terms else None,
            "contract_signed": terms.contract_signed if terms else None,
            "payer_matches_contract": terms.payer_matches_contract if terms else None,
            "identity_verified": transaction.customer.identity_verified,
            "mitigations": transaction.mitigations,
        }
        return self.evaluate(context=context, evidence_items=items, customer_trust=customer_trust)
