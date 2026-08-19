from __future__ import annotations

from collections.abc import Iterable


class RiskMitigationService:
    """展示可核验的真实缓释措施和保障金额，不制造不透明的缓释评分。"""

    supported_types = {
        "DEPOSIT",
        "INSURANCE",
        "GUARANTEE",
        "LETTER_OF_CREDIT",
        "PLATFORM_PROTECTION",
        "PARTIAL_SHIPMENT",
        "ESCROW",
        "OTHER",
    }
    monetary_coverage_types = {"INSURANCE", "GUARANTEE", "LETTER_OF_CREDIT", "PLATFORM_PROTECTION", "ESCROW"}

    @staticmethod
    def _value(item: object | dict, key: str, default=None):
        return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)

    def evaluate(self, *, mitigations: Iterable[object | dict], currency: str, exposure_base: float) -> dict:
        currency = currency.upper()
        verified: list[dict] = []
        unverified: list[dict] = []
        eligible_coverage = 0.0
        for mitigation in mitigations:
            mitigation_type = str(self._value(mitigation, "mitigation_type", "OTHER")).upper()
            if mitigation_type not in self.supported_types:
                mitigation_type = "OTHER"
            item_currency = str(self._value(mitigation, "currency", currency)).upper()
            coverage_amount = max(0.0, float(self._value(mitigation, "coverage_amount", 0) or 0))
            item = {
                "mitigation_type": mitigation_type,
                "verified": bool(self._value(mitigation, "verified", False)),
                "coverage_amount": round(coverage_amount, 2),
                "currency": item_currency,
                "description": str(self._value(mitigation, "description", "") or ""),
            }
            if item["verified"]:
                if item_currency != currency and coverage_amount > 0:
                    item["coverage_eligible"] = False
                    item["reason"] = "币种不一致，缺少汇率快照"
                elif mitigation_type in self.monetary_coverage_types:
                    item["coverage_eligible"] = True
                    eligible_coverage += coverage_amount
                else:
                    item["coverage_eligible"] = False
                verified.append(item)
            else:
                item["coverage_eligible"] = False
                unverified.append(item)
        coverage_amount = min(max(0.0, exposure_base), eligible_coverage)
        return {
            "currency": currency,
            "verified_mitigations": verified,
            "unverified_mitigations": unverified,
            "coverage_amount": round(coverage_amount, 2),
            "coverage_ratio": round(coverage_amount / exposure_base, 4) if exposure_base > 0 else 0,
        }
