from datetime import UTC, datetime, timedelta
from math import log10
from statistics import mean, pstdev

from sqlalchemy.orm import Session

from ...models import CreditScoreHistory, Customer, CustomerTrustSnapshot, Transaction


LEGACY_CREDIT_WEIGHTS = {
    "performance": 0.30,
    "stability": 0.20,
    "dispute": 0.20,
    "identity": 0.15,
    "relationship": 0.15,
}
LEGACY_RISK_LEVEL_THRESHOLDS = [
    {"minimum_score": 90, "label": "低风险优质客户"},
    {"minimum_score": 75, "label": "较低风险"},
    {"minimum_score": 60, "label": "中等风险"},
    {"minimum_score": 40, "label": "较高风险"},
    {"minimum_score": 0, "label": "高风险"},
]


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def risk_level(score: float) -> str:
    return next(
        item["label"]
        for item in LEGACY_RISK_LEVEL_THRESHOLDS
        if score >= item["minimum_score"]
    )


class CreditScoringService:
    """完全由事实数据计算信用分；同一输入始终得到同一输出。"""

    version = "credit_v1"

    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id

    def calculate(self, customer: Customer, save: bool = True) -> tuple[CreditScoreHistory, list[str]]:
        transactions = (
            self.db.query(Transaction)
            .filter(Transaction.merchant_id == self.merchant_id, Transaction.customer_id == customer.id)
            .order_by(Transaction.order_time)
            .all()
        )
        count = len(transactions)
        explanation: list[str] = []

        if count:
            assessed_payments: list[bool] = []
            for tx in transactions:
                due_at = _payment_due_at(tx)
                if due_at is not None and tx.payment_time is not None:
                    assessed_payments.append(tx.payment_time <= due_at)
            paid_on_time = sum(assessed_payments) / len(assessed_payments) if assessed_payments else None
            final_paid = sum(1 for tx in transactions if tx.final_payment_status == "paid") / count
            no_overdue = sum(1 for tx in transactions if tx.overdue_days == 0) / count
            performance_inputs = [final_paid, no_overdue]
            if paid_on_time is not None:
                performance_inputs.append(paid_on_time)
                explanation.append(f"{count} 笔交易中可核验按时付款率 {paid_on_time:.0%}、尾款完成率 {final_paid:.0%}")
            else:
                explanation.append(f"{count} 笔交易缺少明确付款到期日，付款时效未纳入评分；尾款完成率 {final_paid:.0%}")
            performance = mean(performance_inputs) * 100

            amounts = [tx.amount for tx in transactions]
            amount_cv = pstdev(amounts) / mean(amounts) if count > 1 and mean(amounts) else 0
            amount_stability = clamp(100 - amount_cv * 65)
            intervals = [(transactions[i].order_time - transactions[i - 1].order_time).days for i in range(1, count)]
            interval_cv = pstdev(intervals) / mean(intervals) if len(intervals) > 1 and mean(intervals) else 0
            frequency_stability = 65 if count < 3 else clamp(100 - interval_cv * 45)
            category_share = max([sum(1 for tx in transactions if tx.product_category == category) for category in {tx.product_category for tx in transactions}]) / count
            category_stability = category_share * 100
            stability = mean([amount_stability, frequency_stability, category_stability])

            dispute_rate = sum(tx.dispute_status != "none" for tx in transactions) / count
            refund_rate = sum(tx.refund_status != "none" for tx in transactions) / count
            cancel_rate = sum(tx.cancelled for tx in transactions) / count
            dispute = clamp(100 - dispute_rate * 60 - refund_rate * 30 - cancel_rate * 25)
            explanation.append(f"纠纷率 {dispute_rate:.0%}、退款率 {refund_rate:.0%}、取消率 {cancel_rate:.0%}")
        else:
            performance, stability, dispute = 55.0, 50.0, 70.0
            explanation.append("暂无历史交易，交易维度使用审慎的中性基准")

        completeness = sum(bool(value) for value in [customer.name, customer.company_name, customer.country, customer.email, customer.phone, customer.registration_number]) / 6
        identity = clamp((60 if customer.identity_verified else 20) + completeness * 40)
        cooperation_days = (datetime.now(UTC).date() - customer.cooperation_start_date).days if customer.cooperation_start_date else 0
        duration_score = min(100, cooperation_days / 1095 * 100)
        count_score = min(100, count / 20 * 100)
        total_amount = sum(tx.amount for tx in transactions)
        amount_score = min(100, log10(total_amount + 1) / 6 * 100)
        repeat_score = min(100, max(0, count - 1) / 9 * 100)
        relationship = mean([duration_score, count_score, amount_score, repeat_score])

        total = (
            performance * LEGACY_CREDIT_WEIGHTS["performance"]
            + stability * LEGACY_CREDIT_WEIGHTS["stability"]
            + dispute * LEGACY_CREDIT_WEIGHTS["dispute"]
            + identity * LEGACY_CREDIT_WEIGHTS["identity"]
            + relationship * LEGACY_CREDIT_WEIGHTS["relationship"]
        )
        if customer.blacklist_status:
            total = min(total, 25)
            explanation.append("客户已在黑名单中，信用总分被限制在 25 分以内")
        confidence = "低置信度" if count <= 2 else "中置信度" if count <= 9 else "高置信度"
        score = CreditScoreHistory(
            merchant_id=self.merchant_id,
            customer_id=customer.id,
            total_score=round(total, 2),
            performance_score=round(performance, 2),
            stability_score=round(stability, 2),
            dispute_score=round(dispute, 2),
            identity_score=round(identity, 2),
            relationship_score=round(relationship, 2),
            risk_level=risk_level(total),
            confidence_level=confidence,
            rule_version=self.version,
        )
        if save:
            self.db.add(score)
            self.db.flush()
        return score, explanation

    def latest_or_calculate(self, customer: Customer) -> tuple[CreditScoreHistory, list[str]]:
        latest = (
            self.db.query(CreditScoreHistory)
            .filter(CreditScoreHistory.merchant_id == self.merchant_id, CreditScoreHistory.customer_id == customer.id)
            .order_by(CreditScoreHistory.calculated_at.desc(), CreditScoreHistory.id.desc())
            .first()
        )
        return (latest, []) if latest else self.calculate(customer)


def _payment_due_at(transaction: Transaction) -> datetime | None:
    """只根据明确条款推导付款到期时间，绝不使用固定的下单后 7 天假设。"""

    terms = transaction.terms
    if terms is None:
        return None
    if terms.payment_due_date is not None:
        return terms.payment_due_date
    due_type = (terms.final_payment_due_type or "").upper()
    if due_type == "BEFORE_SHIPMENT":
        return transaction.shipping_time
    if due_type == "ON_DELIVERY":
        return transaction.delivery_time
    if terms.credit_days is not None:
        anchor = transaction.delivery_time if due_type == "AFTER_DELIVERY" else transaction.order_time
        return anchor + timedelta(days=max(0, terms.credit_days)) if anchor else None
    return None


class CustomerTrustService:
    """Customer Trust v2：描述历史可信度，不对本次订单金额波动下结论。"""

    version = "customer_trust_v2"
    indicators = [
        "合作时长", "交易次数", "累计交易金额", "历史最大订单", "可核验按期付款率",
        "逾期次数与平均逾期天数", "退款率", "纠纷率", "拒收/取消次数", "身份核验",
    ]
    trust_levels = ["developing", "moderate", "high", "low"]
    confidence_policy = {
        "low": "0–2 笔历史交易",
        "medium": "3–9 笔历史交易",
        "high": "10 笔及以上历史交易",
    }
    unknown_data_policy = "缺少明确付款到期日时，按期付款率返回 unknown，不推断为正常或逾期"

    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id

    def calculate(self, customer: Customer, save: bool = False) -> dict:
        transactions = (
            self.db.query(Transaction)
            .filter(Transaction.merchant_id == self.merchant_id, Transaction.customer_id == customer.id)
            .order_by(Transaction.order_time)
            .all()
        )
        count = len(transactions)
        total_amount = round(sum(tx.amount for tx in transactions), 2)
        max_order_amount = round(max((tx.amount for tx in transactions), default=0), 2)
        cooperation_start = customer.cooperation_start_date
        if cooperation_start is None and transactions:
            cooperation_start = transactions[0].order_time.date()
        cooperation_days = max(0, (datetime.now(UTC).date() - cooperation_start).days) if cooperation_start else 0

        assessed_count = 0
        on_time_count = 0
        observed_overdue_days: list[int] = []
        for transaction in transactions:
            due_at = _payment_due_at(transaction)
            if due_at is None:
                continue
            assessed_count += 1
            if transaction.payment_time is not None:
                overdue_days = max(0, (transaction.payment_time - due_at).days)
                if overdue_days == 0:
                    on_time_count += 1
            else:
                overdue_days = max(0, (datetime.now(UTC).replace(tzinfo=None) - due_at).days)
            overdue_days = max(overdue_days, transaction.overdue_days or 0)
            if overdue_days > 0:
                observed_overdue_days.append(overdue_days)

        on_time_payment_rate = round(on_time_count / assessed_count, 4) if assessed_count else None
        average_overdue_days = round(mean(observed_overdue_days), 2) if observed_overdue_days else (0.0 if assessed_count else None)
        refund_count = sum(tx.refund_status != "none" for tx in transactions)
        dispute_count = sum(tx.dispute_status != "none" for tx in transactions)
        rejection_count = sum(tx.cancelled for tx in transactions)
        refund_rate = round(refund_count / count, 4) if count else None
        dispute_rate = round(dispute_count / count, 4) if count else None
        adverse_rate = (refund_count + dispute_count + rejection_count) / max(1, count)

        if count <= 2:
            confidence = "low"
        elif count <= 9:
            confidence = "medium"
        else:
            confidence = "high"

        if customer.blacklist_status or adverse_rate >= 0.3 or (on_time_payment_rate is not None and on_time_payment_rate < 0.6):
            trust_level = "low"
        elif count <= 2:
            trust_level = "developing"
        elif count >= 10 and customer.identity_verified and adverse_rate <= 0.05 and (on_time_payment_rate is None or on_time_payment_rate >= 0.9):
            trust_level = "high"
        else:
            trust_level = "moderate"

        missing_fields: list[str] = []
        if not customer.identity_verified:
            missing_fields.append("identity_verification")
        if assessed_count == 0:
            missing_fields.append("payment_due_date")
        if not transactions:
            missing_fields.append("transaction_history")

        result = {
            "customer_id": customer.id,
            "transaction_count": count,
            "cooperation_days": cooperation_days,
            "total_amount": total_amount,
            "max_order_amount": max_order_amount,
            "on_time_payment_rate": on_time_payment_rate,
            "payment_timing_assessed_count": assessed_count,
            "overdue_count": len(observed_overdue_days),
            "average_overdue_days": average_overdue_days,
            "refund_count": refund_count,
            "refund_rate": refund_rate,
            "dispute_count": dispute_count,
            "dispute_rate": dispute_rate,
            "rejection_count": rejection_count,
            "identity_verified": customer.identity_verified,
            "trust_level": trust_level,
            "confidence_level": confidence,
            "missing_fields": missing_fields,
            "calculation_version": self.version,
            "reason": "历史履约数据不足" if trust_level == "developing" else "基于已核验的历史履约与争议记录",
        }
        if save:
            self.db.add(CustomerTrustSnapshot(
                merchant_id=self.merchant_id,
                customer_id=customer.id,
                transaction_count=count,
                cooperation_days=cooperation_days,
                total_amount=total_amount,
                max_order_amount=max_order_amount,
                on_time_payment_rate=on_time_payment_rate,
                overdue_count=len(observed_overdue_days),
                average_overdue_days=average_overdue_days,
                refund_rate=refund_rate,
                dispute_rate=dispute_rate,
                rejection_count=rejection_count,
                trust_level=trust_level,
                confidence_level=confidence,
                missing_fields=missing_fields,
                calculation_version=self.version,
            ))
            self.db.flush()
        return result
