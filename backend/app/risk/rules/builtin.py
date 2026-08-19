from collections import Counter
from datetime import timedelta
from statistics import mean, pstdev

from .base import RiskRule


class AmountSurgeRule(RiskRule):
    rule_code, name = "AMOUNT_SURGE", "订单金额超过历史均值倍数"
    def evaluate(self, customer, order, history):
        if not history: return None
        average = mean(tx.amount for tx in history); multiple = order["amount"] / max(average, 1)
        threshold = self.config.get("multiple", 5)
        return self.result(f"本次订单为历史平均金额的 {multiple:.1f} 倍", {"current_amount": order["amount"], "historical_average": round(average, 2), "multiple": round(multiple, 2), "threshold": threshold}) if multiple >= threshold else None


class AmountZScoreRule(RiskRule):
    rule_code, name = "AMOUNT_ZSCORE", "订单金额超过均值加三倍标准差"
    def evaluate(self, customer, order, history):
        if len(history) < 3: return None
        values = [tx.amount for tx in history]; average, deviation = mean(values), pstdev(values)
        zscore = (order["amount"] - average) / max(deviation, 1)
        threshold = self.config.get("zscore", 3)
        return self.result(f"订单金额 Z-score 为 {zscore:.2f}", {"zscore": round(zscore, 2), "mean": round(average, 2), "std": round(deviation, 2)}) if zscore >= threshold else None


class SmallToLargeRule(RiskRule):
    rule_code, name = "SMALL_TO_LARGE", "连续小额试单后突然大额采购"
    def evaluate(self, customer, order, history):
        if len(history) < 5: return None
        recent = history[-5:]; recent_avg = mean(tx.amount for tx in recent)
        small_limit, large_multiple = self.config.get("small_limit", 8000), self.config.get("large_multiple", 5)
        triggered = all(tx.amount <= small_limit for tx in recent) and order["amount"] >= recent_avg * large_multiple
        return self.result("最近 5 笔均为小额交易，本次金额显著放大", {"recent_amounts": [tx.amount for tx in recent], "recent_average": round(recent_avg, 2), "current_amount": order["amount"]}) if triggered else None


class HighFrequencyRule(RiskRule):
    rule_code, name = "HIGH_FREQUENCY", "24 小时内异常高频下单"
    def evaluate(self, customer, order, history):
        recent_count = sum(tx.order_time >= order["order_time"] - timedelta(hours=24) for tx in history)
        threshold = self.config.get("orders_24h", 4)
        return self.result(f"24 小时内累计 {recent_count + 1} 笔订单", {"orders_24h": recent_count + 1, "threshold": threshold}) if recent_count + 1 >= threshold else None


class PaymentChangedRule(RiskRule):
    rule_code, name = "PAYMENT_CHANGED", "付款方式突然改变"
    def evaluate(self, customer, order, history):
        if len(history) < 3: return None
        common = Counter(tx.payment_method for tx in history[-10:]).most_common(1)[0][0]
        return self.result(f"付款方式从常用的 {common} 变为 {order['payment_method']}", {"historical_method": common, "current_method": order["payment_method"]}) if order["payment_method"] != common else None


class CountryChangedRule(RiskRule):
    rule_code, name = "COUNTRY_CHANGED", "收货国家突然改变"
    def evaluate(self, customer, order, history):
        if len(history) < 3: return None
        common = Counter(tx.shipping_country for tx in history[-10:]).most_common(1)[0][0]
        return self.result(f"收货国家从常用的 {common} 变为 {order['shipping_country']}", {"historical_country": common, "current_country": order["shipping_country"]}) if order["shipping_country"] != common else None


class AddressChangedRule(RiskRule):
    rule_code, name = "ADDRESS_VOLATILITY", "短期频繁更换收货地址"
    def evaluate(self, customer, order, history):
        window = order["order_time"] - timedelta(days=self.config.get("window_days", 30))
        addresses = {tx.shipping_address for tx in history if tx.order_time >= window} | {order["shipping_address"]}
        threshold = self.config.get("unique_addresses", 3)
        return self.result(f"最近 30 天使用了 {len(addresses)} 个不同地址", {"unique_address_count": len(addresses), "addresses": list(addresses)}) if len(addresses) >= threshold else None


class CategoryChangedRule(RiskRule):
    rule_code, name = "CATEGORY_CHANGED", "采购品类明显变化"
    def evaluate(self, customer, order, history):
        if len(history) < 4: return None
        common, count = Counter(tx.product_category for tx in history[-10:]).most_common(1)[0]
        share = count / min(10, len(history))
        return self.result(f"历史主要采购 {common}，本次改为 {order['product_category']}", {"dominant_category": common, "dominant_share": round(share, 2), "current_category": order["product_category"]}) if share >= self.config.get("dominant_share", .6) and order["product_category"] != common else None


class ProfileChangeLargeOrderRule(RiskRule):
    rule_code, name = "PROFILE_CHANGE_LARGE_ORDER", "资料变更后立即大额下单"
    def evaluate(self, customer, order, history):
        if not customer.profile_updated_at or not history: return None
        hours = (order["order_time"] - customer.profile_updated_at).total_seconds() / 3600
        average = mean(tx.amount for tx in history)
        triggered = 0 <= hours <= self.config.get("hours", 72) and order["amount"] >= average * self.config.get("multiple", 3)
        return self.result("客户资料变更后短时间内出现显著大额订单", {"hours_since_profile_change": round(hours, 1), "current_amount": order["amount"], "historical_average": round(average, 2)}) if triggered else None


class SplitOrdersRule(RiskRule):
    rule_code, name = "SPLIT_ORDERS", "疑似拆单规避审核"
    def evaluate(self, customer, order, history):
        audit = self.config.get("audit_threshold", 50000); ratio = self.config.get("near_ratio", .75)
        recent = [tx.amount for tx in history if tx.order_time >= order["order_time"] - timedelta(hours=48) and audit * ratio <= tx.amount < audit]
        if audit * ratio <= order["amount"] < audit: recent.append(order["amount"])
        triggered = len(recent) >= self.config.get("min_orders", 3) and sum(recent) >= audit * 2
        return self.result(f"48 小时内 {len(recent)} 笔订单接近审核阈值", {"amounts": recent, "combined_amount": round(sum(recent), 2), "audit_threshold": audit}) if triggered else None


class ConsecutiveAdverseRule(RiskRule):
    rule_code, name = "CONSECUTIVE_ADVERSE", "连续逾期、退款或纠纷"
    def evaluate(self, customer, order, history):
        size = self.config.get("consecutive", 3); recent = history[-size:]
        adverse = [tx for tx in recent if tx.overdue_days > 0 or tx.refund_status != "none" or tx.dispute_status != "none"]
        return self.result(f"最近 {size} 笔中有 {len(adverse)} 笔出现逾期、退款或纠纷", {"adverse_order_numbers": [tx.order_number for tx in adverse]}) if len(recent) == size and len(adverse) == size else None


class NewCustomerLargeOrderRule(RiskRule):
    rule_code, name = "NEW_CUSTOMER_LARGE_ORDER", "新客户首单金额过高"
    def evaluate(self, customer, order, history):
        threshold = self.config.get("amount", 20000)
        return self.result("新客户缺少历史履约证据且首单金额较高", {"current_amount": order["amount"], "threshold": threshold}, 85) if not history and order["amount"] >= threshold else None


class FirstCreditExposureRule(RiskRule):
    rule_code, name = "FIRST_CREDIT_EXPOSURE", "首次合作即产生授信敞口"
    def evaluate(self, customer, order, history):
        credit_days = int(order.get("credit_days") or 0)
        deposit_ratio = float(order.get("deposit_ratio") or 0)
        exposure = max(0, float(order.get("amount") or 0) * (1 - deposit_ratio))
        if not history and (credit_days > 0 or exposure > 0):
            return self.result(
                "客户缺少历史履约记录，本次交易将产生首次授信敞口",
                {"credit_days": credit_days, "deposit_ratio": deposit_ratio, "projected_unpaid_amount": round(exposure, 2)},
            )
        return None


class LowDepositRatioRule(RiskRule):
    rule_code, name = "LOW_DEPOSIT_RATIO", "定金比例偏低"
    def evaluate(self, customer, order, history):
        ratio = order.get("deposit_ratio")
        threshold = float(self.config.get("minimum", 0.3))
        if ratio is not None and float(ratio) < threshold:
            return self.result(
                f"当前定金比例 {float(ratio):.0%}，低于规则阈值 {threshold:.0%}",
                {"deposit_ratio": float(ratio), "minimum_deposit_ratio": threshold},
            )
        return None


class LongCreditTermRule(RiskRule):
    rule_code, name = "LONG_CREDIT_TERM", "账期较长"
    def evaluate(self, customer, order, history):
        credit_days = int(order.get("credit_days") or 0)
        threshold = int(self.config.get("days", 45))
        return self.result(
            f"本次账期为 {credit_days} 天，达到长账期阈值",
            {"credit_days": credit_days, "threshold_days": threshold},
        ) if credit_days >= threshold else None


def _historical_credit_days(transaction) -> int | None:
    if getattr(transaction, "terms", None) and transaction.terms.credit_days is not None:
        return transaction.terms.credit_days
    method = (getattr(transaction, "payment_method", "") or "").lower()
    for days in (120, 90, 60, 45, 30, 15):
        if str(days) in method and ("open account" in method or "days" in method or "天" in method):
            return days
    return None


class CreditTermExtensionRule(RiskRule):
    rule_code, name = "CREDIT_TERM_EXTENSION", "账期较历史水平明显延长"
    def evaluate(self, customer, order, history):
        current = order.get("credit_days")
        historical = [days for days in (_historical_credit_days(tx) for tx in history[-10:]) if days is not None]
        if current is None or not historical:
            return None
        baseline = max(historical)
        extension = int(current) - baseline
        threshold = int(self.config.get("extension_days", 15))
        return self.result(
            f"账期从历史最长 {baseline} 天延长到 {int(current)} 天",
            {"historical_max_credit_days": baseline, "current_credit_days": int(current), "extension_days": extension},
        ) if extension >= threshold else None


class DeferredFinalPaymentRule(RiskRule):
    rule_code, name = "DEFERRED_FINAL_PAYMENT", "尾款延后至发货或交付后"
    def evaluate(self, customer, order, history):
        due_type = str(order.get("final_payment_due_type") or "").upper()
        deferred_types = set(self.config.get("due_types", ["AFTER_SHIPMENT", "ON_DELIVERY", "AFTER_DELIVERY", "CREDIT_TERM"]))
        return self.result(
            "尾款支付节点位于发货或交付后，将增加未收款货值敞口",
            {"final_payment_due_type": due_type},
        ) if due_type in deferred_types else None


class PayerContractMismatchRule(RiskRule):
    rule_code, name = "PAYER_CONTRACT_MISMATCH", "付款主体与合同主体不一致"
    def evaluate(self, customer, order, history):
        return self.result(
            "付款主体与合同约定主体不一致，需要核验第三方付款授权与资金来源",
            {"payer_matches_contract": False},
        ) if order.get("payer_matches_contract") is False else None


class PaymentAccountChangeRule(RiskRule):
    rule_code, name = "PAYMENT_ACCOUNT_CHANGE", "付款账户发生变化"
    def evaluate(self, customer, order, history):
        changed = order.get("payment_account_changed") is True
        verified = order.get("payment_account_verified") is True
        return self.result(
            "付款账户已变更且尚未完成独立核验",
            {"payment_account_changed": changed, "payment_account_verified": verified},
        ) if changed and not verified else None


class AmountAboveHistoricalMaxRule(RiskRule):
    rule_code, name = "AMOUNT_ABOVE_HISTORICAL_MAX", "订单金额超过历史最大订单"
    def evaluate(self, customer, order, history):
        if not history:
            return None
        historical_max = max(tx.amount for tx in history)
        ratio = float(order.get("amount") or 0) / max(historical_max, 1)
        threshold = float(self.config.get("multiple", 1.25))
        return self.result(
            f"本次订单为历史最大订单的 {ratio:.1f} 倍",
            {"current_amount": order.get("amount"), "historical_max": round(historical_max, 2), "multiple": round(ratio, 2), "threshold": threshold},
        ) if ratio >= threshold else None


RULE_CLASSES = [
    AmountSurgeRule,
    AmountZScoreRule,
    SmallToLargeRule,
    HighFrequencyRule,
    PaymentChangedRule,
    CountryChangedRule,
    AddressChangedRule,
    CategoryChangedRule,
    ProfileChangeLargeOrderRule,
    SplitOrdersRule,
    ConsecutiveAdverseRule,
    NewCustomerLargeOrderRule,
    FirstCreditExposureRule,
    LowDepositRatioRule,
    LongCreditTermRule,
    CreditTermExtensionRule,
    DeferredFinalPaymentRule,
    PayerContractMismatchRule,
    PaymentAccountChangeRule,
    AmountAboveHistoricalMaxRule,
]
