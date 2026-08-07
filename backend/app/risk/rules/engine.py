from sqlalchemy.orm import Session

from ...models import Customer, RiskRuleConfig, Transaction
from .builtin import RULE_CLASSES


class RiskRuleEngine:
    version = "rules_v1"

    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id

    def evaluate(self, customer: Customer, order: dict, history: list[Transaction]) -> list[dict]:
        configs = {item.rule_code: item for item in self.db.query(RiskRuleConfig).filter(RiskRuleConfig.enabled.is_(True)).all()}
        results: list[dict] = []
        for rule_class in RULE_CLASSES:
            config = configs.get(rule_class.rule_code)
            if config is None:
                continue
            result = rule_class(config.threshold_config or {}, config.severity).evaluate(customer, order, history)
            if result:
                results.append(result)
        return sorted(results, key=lambda item: item["risk_score"], reverse=True)
