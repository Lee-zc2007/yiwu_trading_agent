from abc import ABC, abstractmethod
from typing import Any

from ...models import Customer, Transaction


class RiskRule(ABC):
    rule_code = "BASE"
    name = "基础规则"

    def __init__(self, config: dict[str, Any], severity: str = "medium"):
        self.config = config
        self.severity = severity

    def result(self, reason: str, evidence: dict, score: float | None = None) -> dict:
        return {
            "triggered": True,
            "rule_code": self.rule_code,
            "rule_name": self.name,
            "risk_level": self.severity,
            "risk_score": score or {"low": 35, "medium": 55, "high": 78, "critical": 92}.get(self.severity, 55),
            "reason": reason,
            "evidence": evidence,
        }

    @abstractmethod
    def evaluate(self, customer: Customer, order: dict, history: list[Transaction]) -> dict | None:
        raise NotImplementedError
