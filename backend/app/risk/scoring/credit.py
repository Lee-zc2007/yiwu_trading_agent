from datetime import UTC, datetime, timedelta
from math import log10
from statistics import mean, pstdev

from sqlalchemy.orm import Session

from ...models import CreditScoreHistory, Customer, Transaction


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def risk_level(score: float) -> str:
    if score >= 90:
        return "低风险优质客户"
    if score >= 75:
        return "较低风险"
    if score >= 60:
        return "中等风险"
    if score >= 40:
        return "较高风险"
    return "高风险"


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
            paid_on_time = sum(1 for tx in transactions if tx.payment_time and tx.payment_time <= tx.order_time + timedelta(days=7)) / count
            final_paid = sum(1 for tx in transactions if tx.final_payment_status == "paid") / count
            no_overdue = sum(1 for tx in transactions if tx.overdue_days == 0) / count
            performance = mean([paid_on_time, final_paid, no_overdue]) * 100
            explanation.append(f"{count} 笔交易中按时付款率 {paid_on_time:.0%}、尾款完成率 {final_paid:.0%}")

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

        total = performance * 0.30 + stability * 0.20 + dispute * 0.20 + identity * 0.15 + relationship * 0.15
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
