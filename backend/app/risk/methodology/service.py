from __future__ import annotations

from sqlalchemy.orm import Session

from ...models import RiskRuleConfig
from ..decision import TransactionDecisionService
from ..evidence import EvidenceCompletenessService
from ..exposure import RiskExposureService
from ..mitigation import RiskMitigationService
from ..rules import RiskRuleEngine
from ..scoring.credit import (
    LEGACY_CREDIT_WEIGHTS,
    LEGACY_RISK_LEVEL_THRESHOLDS,
    CreditScoringService,
    CustomerTrustService,
)
from ..terms import CreditTermsService


class RiskEvaluationCriteriaService:
    """读取系统当前生效的风险评价口径，不执行客户或订单风险计算。

    该服务把代码中真实使用的版本、常量和数据库规则配置转换成只读 DTO，
    避免由 LLM 凭常识解释，也避免在 RAG 中维护一份可能过期的评分标准副本。
    """

    version = "risk_methodology_v1"

    def __init__(self, db: Session):
        self.db = db

    def get(self) -> dict:
        rules = (
            self.db.query(RiskRuleConfig)
            .filter(RiskRuleConfig.enabled.is_(True))
            .order_by(RiskRuleConfig.rule_code)
            .all()
        )
        return {
            "methodology_version": self.version,
            "source_kind": "deterministic_configuration",
            "purpose": "提供数字证据、确定性风险计算和可执行交易条件建议，最终由商户人工决策；不认定客户是否欺诈",
            "customer_trust": {
                "version": CustomerTrustService.version,
                "question_answered": "这个客户过去是否可靠，以及历史数据的可信程度",
                "indicators": list(CustomerTrustService.indicators),
                "trust_levels": list(CustomerTrustService.trust_levels),
                "confidence_policy": dict(CustomerTrustService.confidence_policy),
                "unknown_data_policy": CustomerTrustService.unknown_data_policy,
            },
            "transaction_risk": {
                "version": RiskRuleEngine.version,
                "risk_levels": ["low", "medium", "high", "critical"],
                "enabled_rule_count": len(rules),
                "enabled_rules": [
                    {
                        "rule_code": item.rule_code,
                        "rule_name": item.rule_name,
                        "severity": item.severity,
                        "threshold_config": item.threshold_config or {},
                        "version": item.version,
                    }
                    for item in rules
                ],
                "principle": "本次交易风险由确定性规则最高严重度主导；客户历史可靠不代表当前异常交易自动低风险",
            },
            "risk_exposure": {
                "formulas": dict(RiskExposureService.calculation),
                "eligible_coverage_types": sorted(RiskExposureService.coverage_types),
                "constraints": ["敞口不得为负数", "未核验保障不得抵扣", "币种不一致且无汇率快照时拒绝抵扣"],
            },
            "evidence_completeness": {
                "weights": dict(EvidenceCompletenessService.weights),
                "critical_types": sorted(EvidenceCompletenessService.critical_types),
                "formula": "已核验必需证据权重 / 全部必需证据权重",
                "principle": "大量普通证据不能掩盖关键证据缺失",
            },
            "risk_mitigation": {
                "supported_types": sorted(RiskMitigationService.supported_types),
                "monetary_coverage_types": sorted(RiskMitigationService.monetary_coverage_types),
                "principle": "只有已核验、币种一致且属于可抵扣类型的保障金额才能降低敞口",
            },
            "credit_terms": {
                "statuses": sorted(CreditTermsService.statuses),
                "outputs": ["建议最低定金比例", "建议最长账期", "建议最大敞口", "付款节点", "分批付款/发货", "需补证据"],
                "human_decision_required": True,
            },
            "anomaly_signal": {
                "role": "auxiliary_only",
                "constraints": ["不能单独产生 HIGH", "不能单独产生 CRITICAL", "不能用于认定欺诈"],
            },
            "legacy_credit_reference": {
                "version": CreditScoringService.version,
                "status": "legacy_reference_not_primary_decision",
                "weights": dict(LEGACY_CREDIT_WEIGHTS),
                "risk_level_thresholds": list(LEGACY_RISK_LEVEL_THRESHOLDS),
            },
            "decision_version": TransactionDecisionService.version,
        }
