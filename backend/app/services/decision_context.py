"""Agent 结构化交易决策上下文持久化。

聊天消息用于展示与审计；本服务只保存经过字段白名单约束的业务上下文，二者不混用。
所有查询同时按 merchant_id、user_id、conversation_id 隔离。
"""

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from ..models import AgentDecisionContext
from .conversation_service import normalize_user_id


CONTEXT_FIELDS = {
    "amount",
    "currency",
    "deposit_ratio",
    "deposit_amount",
    "confirmed_payment_amount",
    "credit_days",
    "final_payment_ratio",
    "final_payment_due_type",
    "contract_signed",
    "identity_verified",
    "payer_matches_contract",
    "payment_account_changed",
    "payment_account_verified",
    "shipping_address",
    "shipping_country",
    "product_category",
    "product_name",
    "payment_method",
    "planned_shipping_value",
    "planned_payment_before_shipping",
    "partial_payment",
    "partial_shipment",
    "payment_terms_verified",
    "first_cooperation",
    "customer_name",
    "mitigations",
    "evidence_items",
}


class DecisionContextService:
    """AgentDecisionContext 的 SQLAlchemy 实现；Agent 仅依赖其方法而不接触 Session。"""

    def __init__(self, db: Session, user_id: str = "demo-user"):
        self.db = db
        self.user_id = normalize_user_id(user_id)

    def load(self, merchant_id: int, conversation_id: str) -> dict[str, Any]:
        row = self._row(merchant_id, conversation_id)
        if row is None:
            return {
                "conversation_id": conversation_id,
                "customer_id": None,
                "transaction_id": None,
                "context_version": 1,
                "transaction_context": {},
                "required_fields": [],
                "missing_fields": [],
                "information_completeness": 0.0,
                "next_best_question": "",
            }
        return {
            "conversation_id": row.conversation_id,
            "customer_id": row.customer_id,
            "transaction_id": row.transaction_id,
            "context_version": row.context_version,
            "transaction_context": deepcopy(row.transaction_context or {}),
            "required_fields": list(row.required_fields or []),
            "missing_fields": list(row.missing_fields or []),
            "information_completeness": row.information_completeness,
            "next_best_question": row.next_best_question,
        }

    def save(
        self,
        merchant_id: int,
        conversation_id: str,
        *,
        customer_id: int | None,
        transaction_id: int | None,
        transaction_context: dict[str, Any],
        required_fields: list[str],
        missing_fields: list[str],
        information_completeness: float,
        next_best_question: str,
    ) -> dict[str, Any]:
        row = self._row(merchant_id, conversation_id)
        clean_context = {
            key: self._clean_value(value)
            for key, value in transaction_context.items()
            if key in CONTEXT_FIELDS and value is not None
        }
        if row is None:
            row = AgentDecisionContext(
                merchant_id=merchant_id,
                user_id=self.user_id,
                conversation_id=conversation_id,
                context_version=1,
            )
            self.db.add(row)
        else:
            row.context_version += 1
        row.customer_id = customer_id
        row.transaction_id = transaction_id
        row.transaction_context = clean_context
        row.required_fields = list(dict.fromkeys(required_fields))
        row.missing_fields = list(dict.fromkeys(missing_fields))
        row.information_completeness = max(0.0, min(1.0, float(information_completeness)))
        row.next_best_question = str(next_best_question or "")[:1000]
        self.db.flush()
        return self.load(merchant_id, conversation_id)

    def delete(self, merchant_id: int, conversation_id: str) -> bool:
        row = self._row(merchant_id, conversation_id)
        if row is None:
            return False
        self.db.delete(row)
        self.db.flush()
        return True

    def _row(self, merchant_id: int, conversation_id: str) -> AgentDecisionContext | None:
        if not conversation_id:
            return None
        return self.db.query(AgentDecisionContext).filter(
            AgentDecisionContext.merchant_id == merchant_id,
            AgentDecisionContext.user_id == self.user_id,
            AgentDecisionContext.conversation_id == conversation_id,
        ).first()

    @classmethod
    def _clean_value(cls, value):
        if isinstance(value, str):
            return value[:500]
        if isinstance(value, list):
            return [cls._clean_value(item) for item in value[:50]]
        if isinstance(value, dict):
            return {str(key)[:80]: cls._clean_value(item) for key, item in list(value.items())[:50]}
        return value


__all__ = ["DecisionContextService", "CONTEXT_FIELDS"]
