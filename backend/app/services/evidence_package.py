from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime
from html import escape
from typing import Any

from sqlalchemy.orm import Session

from ..models import (
    Transaction,
    TransactionEvidenceItem,
    TransactionEvidencePackage,
    TransactionMitigation,
    TransactionTimelineEvent,
)
from ..risk.decision import TransactionDecisionService


class TransactionEvidencePackageService:
    """生成可审计、可导出的交易证据包。

    服务只组合商户作用域内已有的结构化数据和证据元数据，不读取 Agent
    会话，也不导出邮箱、电话、完整付款账号或聊天原文。风险结论统一复用
    ``TransactionDecisionService``，避免在证据包中再次实现评分与规则逻辑。
    """

    version = "transaction_evidence_package_v1"

    def __init__(self, db: Session, merchant_id: int):
        self.db = db
        self.merchant_id = merchant_id

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): TransactionEvidencePackageService._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [TransactionEvidencePackageService._json_safe(item) for item in value]
        return value

    @staticmethod
    def _safe_summary(value: str) -> str:
        """对人工摘要做最低限度脱敏；证据包永不包含沟通原文。"""

        text = (value or "").strip()[:500]
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[邮箱已脱敏]", text)
        text = re.sub(r"(?<!\d)(?:\+?\d[\d -]{7,}\d)(?!\d)", "[号码已脱敏]", text)
        return text

    def _assert_scope(self, transaction: Transaction) -> None:
        if transaction.merchant_id != self.merchant_id:
            raise ValueError("交易不属于当前商户")

    def build_data(self, transaction: Transaction) -> dict:
        self._assert_scope(transaction)
        customer = transaction.customer
        terms = transaction.terms
        evidence = self.db.query(TransactionEvidenceItem).filter(
            TransactionEvidenceItem.merchant_id == self.merchant_id,
            TransactionEvidenceItem.transaction_id == transaction.id,
        ).order_by(TransactionEvidenceItem.created_at).all()
        timeline = self.db.query(TransactionTimelineEvent).filter(
            TransactionTimelineEvent.merchant_id == self.merchant_id,
            TransactionTimelineEvent.transaction_id == transaction.id,
        ).order_by(TransactionTimelineEvent.event_time).all()
        mitigations = self.db.query(TransactionMitigation).filter(
            TransactionMitigation.merchant_id == self.merchant_id,
            TransactionMitigation.transaction_id == transaction.id,
        ).order_by(TransactionMitigation.created_at).all()

        def evidence_rows(*types: str) -> list[dict]:
            allowed = set(types)
            return [
                {
                    "evidence_type": item.evidence_type,
                    "status": item.status,
                    "verified": item.verified,
                    "controlled_reference": item.file_reference,
                    "summary": self._safe_summary(item.summary),
                    "checksum": item.checksum,
                    "collected_at": item.collected_at,
                    "verified_at": item.verified_at,
                }
                for item in evidence
                if item.evidence_type.upper() in allowed
            ]

        def event_rows(*types: str) -> list[dict]:
            allowed = set(types)
            return [
                {
                    "event_type": item.event_type,
                    "event_time": item.event_time,
                    "amount": item.amount,
                    "currency": item.currency,
                    "verified": item.verified,
                    "description": self._safe_summary(item.description),
                }
                for item in timeline
                if item.event_type.upper() in allowed
            ]

        decision = TransactionDecisionService(self.db, self.merchant_id).evaluate(transaction=transaction)
        dispute_summary = {
            "status": transaction.dispute_status,
            "refund_status": transaction.refund_status,
            "overdue_days": transaction.overdue_days,
            "cancelled": transaction.cancelled,
            "requires_human_review": transaction.dispute_status != "none" or transaction.overdue_days > 0,
        }
        data = {
            "package_version": self.version,
            "generated_at": datetime.now(UTC).replace(tzinfo=None),
            "customer": {
                "customer_id": customer.id,
                "company_name": customer.company_name,
                "country": customer.country,
                "region": customer.region,
                "industry": customer.industry,
                "identity_verified": customer.identity_verified,
                "blacklist_status": customer.blacklist_status,
                "watchlist_status": customer.watchlist_status,
                "cooperation_start_date": customer.cooperation_start_date,
            },
            "order": {
                "transaction_id": transaction.id,
                "order_number": transaction.order_number,
                "product_category": transaction.product_category,
                "product_name": transaction.product_name,
                "amount": transaction.amount,
                "currency": transaction.currency,
                "order_time": transaction.order_time,
                "payment_method": transaction.payment_method,
                "shipping_country": transaction.shipping_country,
            },
            "contract": {
                "signed": terms.contract_signed if terms else None,
                "credit_days": terms.credit_days if terms else None,
                "payment_due_date": terms.payment_due_date if terms else None,
                "deposit_ratio": terms.deposit_ratio if terms and terms.deposit_ratio is not None else transaction.deposit_ratio,
                "deposit_amount": terms.deposit_amount if terms else None,
                "final_payment_due_type": terms.final_payment_due_type if terms else None,
                "payer_matches_contract": terms.payer_matches_contract if terms else None,
                "payment_account_changed": terms.payment_account_changed if terms else None,
                "payment_account_verified": terms.payment_account_verified if terms else None,
                "evidence": evidence_rows("CONTRACT", "PAYMENT_TERMS", "PAYER_IDENTITY", "IDENTITY"),
            },
            "payment_records": event_rows("PAYMENT", "DEPOSIT", "FINAL_PAYMENT"),
            "shipping_records": event_rows("SHIPMENT", "DELIVERY"),
            "inspection_records": evidence_rows("INSPECTION", "QUALITY_INSPECTION"),
            "important_communication_summaries": evidence_rows("COMMUNICATION", "CHAT_SUMMARY"),
            "delay_records": event_rows("DUE", "OVERDUE", "EXTENSION", "PAYMENT_DELAY"),
            "dispute_records": event_rows("DISPUTE", "REFUND", "REJECTION", "CANCELLATION"),
            "timeline": event_rows(*(item.event_type.upper() for item in timeline)),
            "current_dispute_summary": dispute_summary,
            "mitigations": [
                {
                    "mitigation_type": item.mitigation_type,
                    "verified": item.verified,
                    "coverage_amount": item.coverage_amount,
                    "currency": item.currency,
                    "valid_from": item.valid_from,
                    "valid_until": item.valid_until,
                    "description": self._safe_summary(item.description),
                }
                for item in mitigations
            ],
            "decision": decision,
            "privacy_notice": "本证据包仅含结构化事实、受控文件引用和脱敏摘要，不含沟通原文、联系方式或完整付款账号。",
        }
        return self._json_safe(data)

    @staticmethod
    def render_html(data: dict, checksum: str = "") -> str:
        """渲染自包含 HTML，所有业务值均转义以阻止注入。"""

        customer = data["customer"]
        order = data["order"]
        dispute = data["current_dispute_summary"]
        decision = data["decision"]
        risk = decision.get("transaction_risk", {})
        exposure = decision.get("risk_exposure", {})

        def rows(items: list[dict], empty: str = "暂无记录") -> str:
            if not items:
                return f"<p class='empty'>{escape(empty)}</p>"
            return "<ul>" + "".join(
                f"<li><strong>{escape(str(item.get('event_type') or item.get('evidence_type') or item.get('mitigation_type') or '记录'))}</strong> "
                f"{escape(str(item.get('event_time') or item.get('status') or ''))} "
                f"{escape(str(item.get('amount') or item.get('coverage_amount') or ''))} "
                f"{escape(str(item.get('currency') or ''))} "
                f"{escape(str(item.get('summary') or item.get('description') or ''))}</li>"
                for item in items
            ) + "</ul>"

        return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>TradeGuard AI 交易证据包</title>
<style>body{{font-family:Arial,'Microsoft YaHei',sans-serif;color:#152238;max-width:980px;margin:32px auto;line-height:1.6}}h1{{color:#123b69}}h2{{border-bottom:1px solid #d9e2ec;padding-bottom:6px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.card{{background:#f5f8fb;border:1px solid #d9e2ec;border-radius:8px;padding:12px}}.empty{{color:#718096}}code{{overflow-wrap:anywhere}}footer{{margin-top:32px;color:#64748b;font-size:12px}}</style></head>
<body><h1>TradeGuard AI 交易证据包</h1>
<p>生成时间：{escape(str(data['generated_at']))}　版本：{escape(str(data['package_version']))}</p>
<section><h2>客户与订单</h2><div class="grid"><div class="card">客户：{escape(str(customer['company_name']))}<br>国家/地区：{escape(str(customer['country']))} / {escape(str(customer['region']))}<br>身份核验：{escape(str(customer['identity_verified']))}</div><div class="card">订单：{escape(str(order['order_number']))}<br>金额：{escape(str(order['amount']))} {escape(str(order['currency']))}<br>商品：{escape(str(order['product_name']))}</div><div class="card">风险等级：{escape(str(risk.get('risk_level', 'unknown')))}<br>预计最大敞口：{escape(str(exposure.get('projected_max_exposure', 'unknown')))} {escape(str(exposure.get('currency', order['currency'])))}<br>决策状态：{escape(str(decision.get('decision_status', 'unknown')))}</div></div></section>
<section><h2>合同与付款条款</h2><pre>{escape(json.dumps(data['contract'], ensure_ascii=False, indent=2))}</pre></section>
<section><h2>付款记录</h2>{rows(data['payment_records'])}</section>
<section><h2>发货与验货</h2>{rows(data['shipping_records'])}{rows(data['inspection_records'])}</section>
<section><h2>重要沟通摘要</h2>{rows(data['important_communication_summaries'], '暂无脱敏沟通摘要')}</section>
<section><h2>延期与纠纷</h2>{rows(data['delay_records'])}{rows(data['dispute_records'])}<pre>{escape(json.dumps(dispute, ensure_ascii=False, indent=2))}</pre></section>
<section><h2>完整时间线</h2>{rows(data['timeline'])}</section>
<section><h2>风险缓释</h2>{rows(data['mitigations'])}</section>
<footer>{escape(data['privacy_notice'])}<br>SHA-256：<code>{escape(checksum)}</code></footer></body></html>"""

    def generate(self, transaction: Transaction) -> TransactionEvidencePackage:
        data = self.build_data(transaction)
        canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        row = TransactionEvidencePackage(
            merchant_id=self.merchant_id,
            transaction_id=transaction.id,
            package_data=data,
            html_content=self.render_html(data, checksum),
            checksum=checksum,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def latest(self, transaction_id: int) -> TransactionEvidencePackage | None:
        return self.db.query(TransactionEvidencePackage).filter(
            TransactionEvidencePackage.merchant_id == self.merchant_id,
            TransactionEvidencePackage.transaction_id == transaction_id,
        ).order_by(TransactionEvidencePackage.generated_at.desc(), TransactionEvidencePackage.id.desc()).first()
