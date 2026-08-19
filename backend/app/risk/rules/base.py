from abc import ABC, abstractmethod
from typing import Any

from ...models import Customer, Transaction


class RiskRule(ABC):
    rule_code = "BASE"
    name = "基础规则"

    def __init__(self, config: dict[str, Any], severity: str = "medium"):
        self.config = config
        self.severity = severity

    def result(self, reason: str, evidence: dict, score: float | None = None, contribution: float | None = None) -> dict:
        risk_score = score if score is not None else {"low": 35, "medium": 55, "high": 78, "critical": 92}.get(self.severity, 55)
        risk_contribution = contribution if contribution is not None else {"low": 10, "medium": 25, "high": 45, "critical": 70}.get(self.severity, 25)
        return {
            "triggered": True,
            "rule_code": self.rule_code,
            "rule_name": self.name,
            "severity": self.severity,
            "risk_level": self.severity,
            "risk_score": risk_score,
            "risk_contribution": risk_contribution,
            "reason": reason,
            "evidence": evidence,
        }

    @abstractmethod
    def evaluate(self, customer: Customer, order: dict, history: list[Transaction]) -> dict | None:
        raise NotImplementedError
