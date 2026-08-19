from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from ...models import Transaction, TransactionMitigation, TransactionTimelineEvent


class RiskExposureService:
    """确定性风险敞口计算器，不做汇率推测，也不读取 LLM 输出结论。"""

    coverage_types = {"INSURANCE", "GUARANTEE", "LETTER_OF_CREDIT", "PLATFORM_PROTECTION", "ESCROW"}
    calculation = {
        "current": "max(0, max(已发货货值, 已交付货值) - 已确认收款 - 已验证保障)",
        "projected": "max(0, 计划发货货值 - 发货前计划到账 - 已验证保障)",
    }

    def __init__(self, db: Session | None = None, merchant_id: int | None = None):
        self.db = db
        self.merchant_id = merchant_id

    @staticmethod
    def _value(item: object | dict, key: str, default=None):
        return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)

    def calculate(
        self,
        *,
        order_amount: float,
        currency: str,
        confirmed_payment_amount: float = 0,
        shipped_value: float = 0,
        delivered_value: float = 0,
        planned_shipping_value: float | None = None,
        planned_payment_before_shipping: float = 0,
        mitigations: Iterable[object | dict] = (),
    ) -> dict:
        currency = currency.upper()
        amounts = {
            "order_amount": order_amount,
            "confirmed_payment_amount": confirmed_payment_amount,
            "shipped_value": shipped_value,
            "delivered_value": delivered_value,
            "planned_shipping_value": order_amount if planned_shipping_value is None else planned_shipping_value,
            "planned_payment_before_shipping": planned_payment_before_shipping,
        }
        if any(float(value or 0) < 0 for value in amounts.values()):
            raise ValueError("风险敞口计算不接受负数金额")

        verified_coverage = 0.0
        coverage_items: list[dict] = []
        ignored_items: list[dict] = []
        for mitigation in mitigations:
            item_currency = str(self._value(mitigation, "currency", currency)).upper()
            mitigation_type = str(self._value(mitigation, "mitigation_type", "OTHER")).upper()
            verified = bool(self._value(mitigation, "verified", False))
            coverage = max(0.0, float(self._value(mitigation, "coverage_amount", 0) or 0))
            item = {"mitigation_type": mitigation_type, "coverage_amount": coverage, "currency": item_currency}
            if item_currency != currency and verified and coverage > 0:
                raise ValueError(f"保障币种 {item_currency} 与交易币种 {currency} 不一致，缺少明确汇率快照")
            if verified and mitigation_type in self.coverage_types:
                verified_coverage += coverage
                coverage_items.append(item)
            else:
                ignored_items.append({**item, "reason": "未核验或不是可抵扣的金额保障"})

        gross_current = max(float(shipped_value or 0), float(delivered_value or 0))
        gross_projected = float(amounts["planned_shipping_value"] or 0)
        # 同一保障项只汇总一次，并且不允许显示超过最大可能货值的虚高保障。
        coverage_amount = min(verified_coverage, max(gross_current, gross_projected, 0))
        current_exposure = max(0.0, gross_current - float(confirmed_payment_amount or 0) - coverage_amount)
        projected_max_exposure = max(
            0.0,
            gross_projected - float(planned_payment_before_shipping or 0) - coverage_amount,
        )
        return {
            "currency": currency,
            "order_amount": round(float(order_amount), 2),
            "confirmed_payment_amount": round(float(confirmed_payment_amount or 0), 2),
            "shipped_or_delivered_value": round(gross_current, 2),
            "planned_shipping_value": round(gross_projected, 2),
            "planned_payment_before_shipping": round(float(planned_payment_before_shipping or 0), 2),
            "current_exposure": round(current_exposure, 2),
            "projected_max_exposure": round(projected_max_exposure, 2),
            "coverage_amount": round(coverage_amount, 2),
            "coverage_ratio": round(coverage_amount / order_amount, 4) if order_amount else 0,
            "verified_coverage_items": coverage_items,
            "ignored_mitigations": ignored_items,
            "calculation": dict(self.calculation),
        }

    def for_transaction(self, transaction: Transaction) -> dict:
        if self.db is None or self.merchant_id is None:
            raise RuntimeError("按交易计算敞口需要数据库会话和 merchant_id")
        if transaction.merchant_id != self.merchant_id:
            raise ValueError("交易不属于当前商户")
        events = self.db.query(TransactionTimelineEvent).filter(
            TransactionTimelineEvent.merchant_id == self.merchant_id,
            TransactionTimelineEvent.transaction_id == transaction.id,
            TransactionTimelineEvent.verified.is_(True),
        ).all()
        payments = sum(event.amount or 0 for event in events if event.event_type == "PAYMENT")
        shipped = sum(event.amount or 0 for event in events if event.event_type == "SHIPMENT")
        delivered = sum(event.amount or 0 for event in events if event.event_type == "DELIVERY")
        terms = transaction.terms
        deposit_amount = (terms.deposit_amount if terms else None)
        if not payments and deposit_amount:
            payments = deposit_amount
        planned_shipping = terms.planned_shipping_value if terms and terms.planned_shipping_value is not None else transaction.amount
        planned_payment = terms.planned_payment_before_shipping if terms and terms.planned_payment_before_shipping is not None else payments
        mitigations = self.db.query(TransactionMitigation).filter(
            TransactionMitigation.merchant_id == self.merchant_id,
            TransactionMitigation.transaction_id == transaction.id,
        ).all()
        return self.calculate(
            order_amount=transaction.amount,
            currency=transaction.currency,
            confirmed_payment_amount=payments,
            shipped_value=shipped or (transaction.amount if transaction.shipping_time else 0),
            delivered_value=delivered or (transaction.amount if transaction.delivery_time else 0),
            planned_shipping_value=planned_shipping,
            planned_payment_before_shipping=planned_payment,
            mitigations=mitigations,
        )
