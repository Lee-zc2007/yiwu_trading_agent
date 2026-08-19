"""Agent 交易字段抽取、确定性合并与主动追问策略。"""

from __future__ import annotations

import re
from typing import Any


REQUIRED_FIELDS = [
    "amount",
    "currency",
    "deposit_ratio",
    "credit_days",
    "identity_verified",
    "contract_signed",
    "payer_matches_contract",
]

QUESTION_PRIORITY = [
    ("deposit_ratio", "这笔订单客户计划支付多少比例的定金？"),
    ("identity_verified", "客户企业身份是否已经通过独立核验？"),
    ("contract_signed", "正式合同是否已经签署？"),
    ("payer_matches_contract", "付款主体是否与合同主体一致？"),
    ("credit_days", "客户希望获得多少天账期？如果不放账请回复 0 天。"),
    ("amount", "这笔订单的总金额是多少？"),
    ("currency", "订单使用什么币种？"),
]


class TransactionContextExtractor:
    """离线可用的确定性抽取器；未来可用结构化 LLM 输出补充，但不能计算风险。"""

    def extract(self, message: str, existing: dict[str, Any] | None = None, missing_fields: list[str] | None = None) -> dict[str, Any]:
        text = str(message or "").strip()
        lower = text.lower()
        patch: dict[str, Any] = {}

        amount_patterns = [
            r"(?:\$|usd\s*)([\d,]+(?:\.\d+)?)",
            r"([\d,]+(?:\.\d+)?)\s*(万)?\s*(美元|美金|usd|人民币|元|cny)",
        ]
        match = re.search(amount_patterns[0], lower, re.I)
        if match:
            patch["amount"] = float(match.group(1).replace(",", ""))
            patch["currency"] = "USD"
        else:
            match = re.search(amount_patterns[1], lower, re.I)
            if match:
                value = float(match.group(1).replace(",", ""))
                if match.group(2):
                    value *= 10000
                patch["amount"] = value
                patch["currency"] = "USD" if match.group(3).lower() in {"美元", "美金", "usd"} else "CNY"

        deposit_match = re.search(r"(?:定金(?:比例)?\s*(?:是|为|提高到|改成|调整到)?\s*)?(\d+(?:\.\d+)?)\s*%\s*(?:定金)?", text)
        if deposit_match and ("定金" in text or "deposit" in lower or "deposit_ratio" in (missing_fields or [])):
            patch["deposit_ratio"] = float(deposit_match.group(1)) / 100
        credit_match = re.search(r"(?:账期(?:从\s*\d+\s*天)?\s*(?:是|为|改成|调整到|缩短到|延长到)?\s*)?(\d+)\s*天\s*(?:账期|赊账)?", text)
        if credit_match and ("账期" in text or "赊账" in text or "credit_days" in (missing_fields or [])):
            patch["credit_days"] = int(credit_match.group(1))

        if any(phrase in text for phrase in ["第一次合作", "首次合作", "新客户"]):
            patch["first_cooperation"] = True
        if any(phrase in text for phrase in ["已经核验企业身份", "身份已核验", "企业身份已核验", "身份核验通过"]):
            patch["identity_verified"] = True
        elif any(phrase in text for phrase in ["身份未核验", "还没核验身份", "未完成身份核验"]):
            patch["identity_verified"] = False
        if any(phrase in text for phrase in ["合同已经签", "合同已签", "正式合同签了", "合同也签了"]):
            patch["contract_signed"] = True
        elif any(phrase in text for phrase in ["合同未签", "还没签合同", "没有正式合同"]):
            patch["contract_signed"] = False
        if any(phrase in text for phrase in ["付款主体一致", "付款方一致", "付款主体与合同主体一致"]):
            patch["payer_matches_contract"] = True
        elif any(phrase in text for phrase in ["付款主体不一致", "第三方付款", "代付"]):
            patch["payer_matches_contract"] = False
        if any(phrase in text for phrase in ["付款账户变了", "更换付款账户", "付款账户也换了", "收款账户变更"]):
            patch["payment_account_changed"] = True
        if any(phrase in text for phrase in ["新账户已核验", "付款账户已核验"]):
            patch["payment_account_verified"] = True
        if any(phrase in text for phrase in ["分批发货", "分批出货"]):
            patch["partial_shipment"] = True
        if any(phrase in text for phrase in ["分批付款", "分期付款"]):
            patch["partial_payment"] = True

        due_types = {
            "发货前付尾款": "BEFORE_SHIPMENT",
            "交付时付尾款": "ON_DELIVERY",
            "交付后付尾款": "AFTER_DELIVERY",
            "发货后付尾款": "AFTER_SHIPMENT",
        }
        for phrase, value in due_types.items():
            if phrase in text:
                patch["final_payment_due_type"] = value
                break
        if patch.get("contract_signed") is True and (patch.get("credit_days") is not None or (existing or {}).get("credit_days") is not None):
            patch["payment_terms_verified"] = True
        return patch


def merge_context(existing: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """只覆盖明确抽取到的非空字段；列表字段也不做隐式追加。"""

    merged = dict(existing or {})
    for key, value in patch.items():
        if value is not None:
            merged[key] = value
    if merged.get("contract_signed") is True and merged.get("credit_days") is not None:
        merged["payment_terms_verified"] = True
    return merged


def required_field_status(context: dict[str, Any]) -> tuple[list[str], list[str], float, str]:
    required = list(REQUIRED_FIELDS)
    missing = [field for field in required if context.get(field) is None]
    completeness = round((len(required) - len(missing)) / len(required), 4)
    next_question = next((question for field, question in QUESTION_PRIORITY if field in missing), "")
    return required, missing, completeness, next_question


__all__ = ["TransactionContextExtractor", "merge_context", "required_field_status", "REQUIRED_FIELDS"]
