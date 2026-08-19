"""Agent 白名单 Tool 调用层。

本模块是 Schema 驱动的薄适配层，只负责四件事：校验输入、调用只读业务网关、
校验输出、封装异常与证据引用。交易统计、客户对比、核验清单、信用评分、规则
判断和异常检测都不在 Tool 中实现。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .schemas import AgentDataGateway, EvidenceRef, ToolResult


logger = logging.getLogger(__name__)


class ToolSchema(BaseModel):
    """所有 Tool Schema 的严格基类，拒绝模型偷偷添加未声明参数。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class CustomerProfileInput(ToolSchema):
    """获取外商基本信息的输入。"""

    customer_id: int = Field(gt=0, description="外商唯一标识")


class CustomerProfileOutput(ToolSchema):
    """脱敏后的外商基本信息。"""

    customer_id: int = Field(description="外商唯一标识")
    company_name: str = Field(description="企业名称")
    contact_name: str = Field(description="联系人姓名")
    country: str = Field(description="所在国家")
    region: str = Field(description="所在区域")
    industry: str = Field(description="所属行业")
    cooperation_start_date: date | None = Field(description="合作开始日期")
    identity_verified: bool = Field(description="身份认证状态")
    registration_number: str = Field(description="企业注册号")
    main_product_category: str = Field(description="主营商品品类")
    email: str = Field(description="脱敏邮箱")
    phone: str = Field(description="脱敏电话")


class CustomerCreditScoreInput(ToolSchema):
    """读取已有信用评分的输入。"""

    customer_id: int = Field(gt=0, description="外商唯一标识")


class CustomerCreditScoreOutput(ToolSchema):
    """数据库中已经保存的最新信用评分；不是 Agent 计算结果。"""

    score_id: int = Field(validation_alias="id", description="信用评分历史记录标识")
    customer_id: int = Field(description="外商唯一标识")
    total_score: float = Field(ge=0, le=100, description="信用总分")
    risk_level: str = Field(description="信用风险等级")
    performance_score: float = Field(ge=0, le=100, description="履约表现分")
    stability_score: float = Field(ge=0, le=100, description="交易稳定分")
    dispute_score: float = Field(ge=0, le=100, description="纠纷控制分")
    identity_score: float = Field(ge=0, le=100, description="身份可信分")
    relationship_score: float = Field(ge=0, le=100, description="合作关系分")
    confidence_level: str = Field(description="评分置信度")
    rule_version: str = Field(description="评分规则版本")
    calculated_at: datetime = Field(description="评分生成时间")
    reasons: list[str] = Field(description="基于已保存分项分的说明")


class CustomerTransactionsInput(ToolSchema):
    """查询历史交易的输入。"""

    customer_id: int = Field(gt=0, description="外商唯一标识")
    limit: int = Field(default=10, ge=1, le=50, description="最近交易返回数量")


class TransactionRecordOutput(ToolSchema):
    """单笔历史交易摘要。"""

    order_id: int = Field(description="订单唯一标识")
    order_number: str = Field(description="订单编号")
    product_category: str = Field(description="商品品类")
    product_name: str = Field(description="商品名称")
    amount: float = Field(description="订单金额")
    currency: str = Field(description="币种")
    order_time: datetime = Field(description="下单时间")
    payment_method: str = Field(description="付款方式")
    final_payment_status: str = Field(description="尾款状态")
    refund_status: str = Field(description="退款状态")
    dispute_status: str = Field(description="纠纷状态")
    overdue_days: int = Field(ge=0, description="逾期天数")
    shipping_country: str = Field(description="收货国家")


class TransactionTrendPointOutput(ToolSchema):
    """用于展示订单金额趋势的数据点。"""

    order_id: int = Field(description="订单唯一标识")
    order_time: datetime = Field(description="下单时间")
    amount: float = Field(description="订单金额")


class CustomerTransactionsOutput(ToolSchema):
    """历史交易与已有数据的统计摘要。"""

    customer_id: int = Field(description="外商唯一标识")
    transaction_count: int = Field(ge=0, description="历史交易总次数")
    average_order_amount: float = Field(ge=0, description="历史平均订单金额")
    total_transaction_amount: float = Field(ge=0, description="历史累计交易金额")
    recent_transactions: list[TransactionRecordOutput] = Field(description="最近交易")
    transaction_trend: list[TransactionTrendPointOutput] = Field(description="按时间排列的交易金额趋势")


class OrderRiskAnalysisInput(ToolSchema):
    """调用既有订单风控能力的输入。"""

    order_id: int = Field(gt=0, description="需要分析的已有订单标识")


class TriggeredRuleOutput(ToolSchema):
    """现有规则引擎返回的一条命中结果。"""

    triggered: bool = Field(description="规则是否命中")
    rule_code: str = Field(description="规则编码")
    rule_name: str = Field(description="规则名称")
    risk_level: str = Field(description="规则风险等级")
    risk_score: float = Field(ge=0, le=100, description="规则风险分")
    severity: str = Field(description="规则严重度")
    risk_contribution: float = Field(ge=0, le=100, description="可解释的风险贡献")
    reason: str = Field(description="命中原因")
    evidence: dict[str, Any] = Field(description="规则证据快照")


class OrderRiskAnalysisOutput(ToolSchema):
    """既有规则引擎、异常检测和信用评分服务的组合结果。"""

    customer_id: int = Field(description="外商唯一标识")
    order_id: int = Field(description="订单唯一标识")
    risk_event_id: int | None = Field(description="只读运行不会生成风险事件，因此通常为空")
    overall_risk_score: float = Field(ge=0, le=100, description="现有风控服务输出的综合风险分")
    risk_level: str = Field(description="订单风险等级")
    credit_score: float = Field(ge=0, le=100, description="读取的已有信用分")
    credit_confidence: str = Field(description="已有信用分置信度")
    anomaly_score: float = Field(ge=0, le=1, description="异常检测模型分")
    statistical_anomaly_score: float = Field(ge=0, le=1, description="统计异常分")
    triggered_rules: list[TriggeredRuleOutput] = Field(description="规则引擎命中结果")
    abnormal_reasons: list[str] = Field(description="异常与风险原因")
    recommendations: list[str] = Field(description="现有风控服务给出的建议措施")
    model_version: str = Field(description="异常检测模型版本")
    model_status: str = Field(description="异常检测模型状态")
    rule_version: str = Field(description="风险规则版本")
    disclaimer: str = Field(description="风控结果免责声明")
    feature_snapshot: dict[str, float] = Field(description="异常检测特征快照")
    anomaly_signal: dict[str, Any] = Field(description="只作辅助判断的行为异常信号")
    analysis_source: str = Field(description="分析来源，固定为只读运行")


class RiskAlertsInput(ToolSchema):
    """查询风险预警的输入。"""

    customer_id: int | None = Field(default=None, gt=0, description="可选的外商标识；为空时查询当前商户")
    limit: int = Field(default=10, ge=1, le=50, description="最多返回的预警数量")


class RiskAlertOutput(ToolSchema):
    """一条已经保存的风险预警。"""

    id: int = Field(description="风险事件标识")
    customer_id: int = Field(description="外商唯一标识")
    order_id: int | None = Field(description="关联订单标识")
    risk_type: str = Field(description="风险类型")
    risk_level: str = Field(description="风险等级")
    risk_score: float = Field(ge=0, le=100, description="已保存风险分")
    title: str = Field(description="预警标题")
    description: str = Field(description="预警说明")
    triggered_rules: list[dict[str, Any]] = Field(description="已保存的规则命中结果")
    evidence: dict[str, Any] = Field(description="已保存的证据快照")
    status: str = Field(description="处置状态")
    created_at: datetime = Field(description="创建时间")


class RiskAlertsOutput(ToolSchema):
    """风险预警分页摘要。"""

    total: int = Field(ge=0, description="符合条件的预警总数")
    items: list[RiskAlertOutput] = Field(description="风险预警列表")


class CompareCustomersInput(ToolSchema):
    """比较两个外商的输入。"""

    customer_id_a: int = Field(gt=0, description="第一个外商标识")
    customer_id_b: int = Field(gt=0, description="第二个外商标识")

    @model_validator(mode="after")
    def customers_must_differ(self):
        if self.customer_id_a == self.customer_id_b:
            raise ValueError("必须选择两个不同的外商")
        return self


class CustomerRiskComparisonOutput(ToolSchema):
    """单个外商参与风险比较的事实指标。"""

    customer_id: int = Field(description="外商唯一标识")
    company_name: str = Field(description="企业名称")
    country: str = Field(description="所在国家")
    identity_verified: bool = Field(description="身份认证状态")
    credit_score: float | None = Field(description="已有信用分")
    credit_risk_level: str | None = Field(description="信用风险等级")
    credit_confidence: str | None = Field(description="信用分置信度")
    transaction_count: int = Field(ge=0, description="历史交易次数")
    average_order_amount: float = Field(ge=0, description="平均订单金额")
    total_transaction_amount: float = Field(ge=0, description="累计交易金额")
    risk_alert_count: int = Field(ge=0, description="历史风险预警数")
    highest_alert_score: float | None = Field(default=None, ge=0, le=100, description="最高预警分")
    highest_alert_level: str | None = Field(default=None, description="最高优先级预警的等级")


class CompareCustomersOutput(ToolSchema):
    """两个外商的并列事实对比，不包含 Agent 自行评分。"""

    customer_ids: list[int] = Field(min_length=2, max_length=2, description="参与比较的外商标识")
    customers: list[CustomerRiskComparisonOutput] = Field(min_length=2, max_length=2, description="外商风险事实")
    comparison_dimensions: list[str] = Field(description="比较维度")


class VerificationChecklistInput(ToolSchema):
    """生成人工核验清单的输入。"""

    customer_id: int = Field(gt=0, description="外商唯一标识")


class VerificationItemOutput(ToolSchema):
    """一条人工核验事项。"""

    code: str = Field(description="核验项编码")
    item: str = Field(description="核验动作")
    priority: str = Field(description="核验优先级")
    basis: str = Field(description="生成该核验项的已有风险依据")


class VerificationChecklistOutput(ToolSchema):
    """根据已有预警生成的人工核验清单。"""

    customer_id: int = Field(description="外商唯一标识")
    company_name: str = Field(description="企业名称")
    highest_risk_level: str = Field(description="已有预警中的最高风险等级")
    based_on_alert_count: int = Field(ge=0, description="作为依据的历史预警总数")
    risk_event_ids: list[int] = Field(description="作为依据返回的风险事件标识")
    items: list[VerificationItemOutput] = Field(description="人工核验事项")


class RiskEventDetailInput(ToolSchema):
    """兼容已有风险事件解释能力的输入。"""

    event_id: int = Field(gt=0, description="风险事件标识")


class RiskKnowledgeSearchInput(ToolSchema):
    """在非结构化风控知识库中执行语义检索。"""

    query: str = Field(min_length=2, max_length=1000, description="用户的风险知识问题，不得传入 SQL")
    category: Literal[
        "risk_case",
        "yiwu_market_experience",
        "contract_risk_rule",
        "risk_operation_standard",
    ] | None = Field(default=None, description="可选知识分类")
    limit: int = Field(default=5, ge=1, le=10, description="最多召回的知识块数量")


class RiskKnowledgeItemOutput(ToolSchema):
    """一条由 pgvector 相似度检索召回的知识块。"""

    knowledge_id: int = Field(description="知识块标识")
    title: str = Field(description="知识文档标题")
    content: str = Field(description="召回的非结构化文本块")
    category: str = Field(description="知识分类")
    similarity: float = Field(ge=-1, le=1, description="余弦相似度")


class RiskKnowledgeSearchOutput(ToolSchema):
    """RAG 检索结果，明确标记为非结构化知识来源。"""

    query: str
    source_kind: Literal["unstructured_knowledge"]
    retrieval_method: str
    embedding_provider: str
    items: list[RiskKnowledgeItemOutput]


class RiskEvaluationCriteriaInput(ToolSchema):
    """系统评价标准不依赖客户或订单参数。"""


class RiskEvaluationCriteriaOutput(ToolSchema):
    """从当前规则配置与确定性 Service 常量读取的评价口径。"""

    methodology_version: str
    source_kind: Literal["deterministic_configuration"]
    purpose: str
    customer_trust: dict[str, Any]
    transaction_risk: dict[str, Any]
    risk_exposure: dict[str, Any]
    evidence_completeness: dict[str, Any]
    risk_mitigation: dict[str, Any]
    credit_terms: dict[str, Any]
    anomaly_signal: dict[str, Any]
    legacy_credit_reference: dict[str, Any]
    decision_version: str


class TransactionDecisionInput(ToolSchema):
    """草稿或已有交易的统一决策输入。"""

    transaction_context: dict[str, Any] = Field(default_factory=dict, description="已抽取并确定性合并的交易上下文")
    customer_id: int | None = Field(default=None, gt=0)
    transaction_id: int | None = Field(default=None, gt=0)


class TransactionRiskOutput(ToolSchema):
    risk_level: str
    risk_score: float = Field(ge=0, le=100)
    triggered_rules: list[dict[str, Any]]
    main_reasons: list[str]
    rule_version: str


class RiskExposureOutput(ToolSchema):
    currency: str
    order_amount: float
    confirmed_payment_amount: float
    shipped_or_delivered_value: float
    planned_shipping_value: float
    planned_payment_before_shipping: float
    current_exposure: float
    projected_max_exposure: float
    coverage_amount: float
    coverage_ratio: float
    verified_coverage_items: list[dict[str, Any]]
    ignored_mitigations: list[dict[str, Any]]
    calculation: dict[str, str]


class EvidenceCompletenessOutput(ToolSchema):
    completeness: float = Field(ge=0, le=1)
    verified_weight: float
    required_weight: float
    required: list[dict[str, Any]]
    verified: list[str]
    missing: list[str]
    critical_missing: list[str]
    calculation: str


class TransactionDecisionOutput(ToolSchema):
    customer_trust: dict[str, Any]
    transaction_risk: dict[str, Any]
    risk_exposure: dict[str, Any]
    evidence: dict[str, Any]
    mitigations: dict[str, Any]
    anomaly_signal: dict[str, Any]
    credit_terms: dict[str, Any]
    decision_status: str
    main_risks: list[str]
    missing_information: list[str]
    recommendations: list[str]
    calculation_version: str
    disclaimer: str


class TransactionSimulationInput(ToolSchema):
    base_context: dict[str, Any]
    adjustments: dict[str, Any]
    customer_id: int | None = Field(default=None, gt=0)
    transaction_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def adjustments_are_safe(self):
        allowed = {
            "deposit_ratio", "deposit_amount", "confirmed_payment_amount", "credit_days",
            "final_payment_ratio", "final_payment_due_type", "planned_shipping_value",
            "planned_payment_before_shipping", "contract_signed", "payer_matches_contract",
            "payment_account_changed", "payment_account_verified", "partial_payment",
            "partial_shipment", "mitigations",
        }
        unsupported = sorted(set(self.adjustments) - allowed)
        if unsupported:
            raise ValueError("不支持模拟修改字段：" + ", ".join(unsupported))
        return self


class TransactionSimulationOutput(ToolSchema):
    adjustments: dict[str, Any]
    before: dict[str, Any]
    after: dict[str, Any]
    comparison: dict[str, Any]
    persisted: Literal[False]


class TransactionTimelineInput(ToolSchema):
    transaction_id: int = Field(gt=0)


class TransactionTimelineOutput(ToolSchema):
    transaction_id: int
    items: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Tool 名称、说明、输入输出 Schema 与网关调用函数。"""

    name: str
    description: str
    input_schema: type[ToolSchema]
    output_schema: type[ToolSchema]
    handler: Callable[[ToolSchema], dict | None]


class AgentToolRegistry:
    """封装白名单注册、Schema 生成、统一校验和异常处理。"""

    def __init__(self, gateway: AgentDataGateway):
        self.gateway = gateway
        definitions = [
            ToolDefinition("get_customer_profile", "获取外商企业、国家、行业、合作时间与认证状态", CustomerProfileInput, CustomerProfileOutput, self._profile),
            ToolDefinition("get_customer_credit_score", "读取已经保存的最新信用总分、风险等级、分项分、置信度与原因；不会重新计算", CustomerCreditScoreInput, CustomerCreditScoreOutput, self._credit),
            ToolDefinition("get_customer_transactions", "查询外商最近交易、平均订单金额、交易次数和金额趋势", CustomerTransactionsInput, CustomerTransactionsOutput, self._transactions),
            ToolDefinition("get_order_risk_analysis", "调用现有规则引擎、异常检测和已有信用评分，对已有订单执行只读风险分析", OrderRiskAnalysisInput, OrderRiskAnalysisOutput, self._order_risk),
            ToolDefinition("list_risk_alerts", "查询当前商户或指定外商已经保存的风险预警", RiskAlertsInput, RiskAlertsOutput, self._alerts),
            ToolDefinition("compare_customers", "基于已有信用、交易和预警事实比较两个外商的风险情况", CompareCustomersInput, CompareCustomersOutput, self._compare),
            ToolDefinition("generate_verification_checklist", "根据指定外商已有风险预警生成人工核验清单", VerificationChecklistInput, VerificationChecklistOutput, self._checklist),
            # 保留 MVP 已有的风险事件解释工具，避免升级破坏现有会话能力。
            ToolDefinition("get_risk_event_detail", "读取一条已经保存的风险事件及证据快照", RiskEventDetailInput, RiskAlertOutput, self._event_detail),
            ToolDefinition(
                "search_risk_knowledge",
                "使用 RAG 查询外贸风险案例、义乌市场经验、合同风险规则和风控操作规范；不得用于查询交易数据",
                RiskKnowledgeSearchInput,
                RiskKnowledgeSearchOutput,
                self._knowledge,
            ),
            ToolDefinition(
                "get_risk_evaluation_criteria",
                "读取系统当前生效的客户可信度、交易规则、敞口公式、证据权重、风险缓释、授信条件与异常信号边界；回答系统评价标准时必须使用",
                RiskEvaluationCriteriaInput,
                RiskEvaluationCriteriaOutput,
                self._risk_evaluation_criteria,
            ),
            ToolDefinition("get_transaction_risk", "读取确定性交易规则风险；异常模型只作为辅助信号", TransactionDecisionInput, TransactionRiskOutput, self._transaction_risk),
            ToolDefinition("calculate_risk_exposure", "确定性计算当前与预计最大风险敞口", TransactionDecisionInput, RiskExposureOutput, self._risk_exposure),
            ToolDefinition("get_evidence_completeness", "按必需证据权重检查证据完整度与关键缺失项", TransactionDecisionInput, EvidenceCompletenessOutput, self._evidence_completeness),
            ToolDefinition("evaluate_credit_terms", "调用统一交易决策服务生成客户信任、交易风险、敞口、证据和授信条件建议", TransactionDecisionInput, TransactionDecisionOutput, self._credit_terms),
            ToolDefinition("simulate_transaction_adjustment", "只在内存中模拟定金、账期、付款或发货条件调整，不修改正式交易", TransactionSimulationInput, TransactionSimulationOutput, self._simulate_adjustment),
            ToolDefinition("get_transaction_timeline", "读取已有交易的付款、发货、交付、延期和争议时间线", TransactionTimelineInput, TransactionTimelineOutput, self._timeline),
        ]
        self._tools = {item.name: item for item in definitions}

    @property
    def names(self) -> list[str]:
        """返回 Tool 白名单。"""

        return list(self._tools)

    def execute(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        """通过统一入口安全执行 Tool，并始终返回结构化结果。"""

        supplied = arguments or {}
        definition = self._tools.get(name)
        if not definition:
            return self._error(name, supplied, "TOOL_NOT_ALLOWED", "工具不在允许列表中")

        try:
            validated_input = definition.input_schema.model_validate(supplied)
        except ValidationError as exc:
            return self._error(name, supplied, "TOOL_INPUT_INVALID", self._validation_message(exc))

        normalized_arguments = validated_input.model_dump(mode="json")
        try:
            raw_data = definition.handler(validated_input)
            if raw_data is None:
                raise LookupError("没有找到符合条件的业务数据")
        except LookupError as exc:
            return self._error(name, normalized_arguments, "BUSINESS_DATA_NOT_FOUND", str(exc))
        except Exception:
            logger.exception("Agent Tool 执行失败: %s", name)
            return self._error(name, normalized_arguments, "TOOL_EXECUTION_ERROR", "业务能力暂时不可用，请稍后重试")

        try:
            output = definition.output_schema.model_validate(raw_data).model_dump(mode="json")
        except ValidationError as exc:
            logger.error("Agent Tool 输出不符合 Schema: %s: %s", name, exc)
            return self._error(name, normalized_arguments, "TOOL_OUTPUT_INVALID", "业务数据格式与 Tool 输出契约不一致")

        evidence, customer_ids, order_ids, event_ids = self._metadata(name, output)
        return ToolResult(
            tool=name,
            arguments=normalized_arguments,
            data=output,
            summary=self._summary(name, output),
            evidence=evidence,
            customer_ids=customer_ids,
            order_ids=order_ids,
            event_ids=event_ids,
        )

    def llm_specs(self) -> list[dict[str, Any]]:
        """从 Pydantic 输入 Schema 自动生成 GPT/Qwen 等模型的 Tool Calling 定义。"""

        return [
            {
                "type": "function",
                "function": {
                    "name": definition.name,
                    "description": definition.description,
                    "parameters": definition.input_schema.model_json_schema(),
                },
            }
            for definition in self._tools.values()
        ]

    def _profile(self, payload: ToolSchema) -> dict | None:
        data = self._as(payload, CustomerProfileInput)
        return self.gateway.get_customer_profile(data.customer_id)

    def _credit(self, payload: ToolSchema) -> dict | None:
        data = self._as(payload, CustomerCreditScoreInput)
        return self.gateway.get_latest_credit_score(data.customer_id)

    def _transactions(self, payload: ToolSchema) -> dict | None:
        data = self._as(payload, CustomerTransactionsInput)
        return self.gateway.get_customer_transactions(data.customer_id, data.limit)

    def _order_risk(self, payload: ToolSchema) -> dict | None:
        data = self._as(payload, OrderRiskAnalysisInput)
        return self.gateway.analyze_order_risk(data.order_id)

    def _alerts(self, payload: ToolSchema) -> dict:
        data = self._as(payload, RiskAlertsInput)
        return self.gateway.list_risk_alerts(data.customer_id, data.limit)

    def _compare(self, payload: ToolSchema) -> dict | None:
        data = self._as(payload, CompareCustomersInput)
        return self.gateway.compare_customers(data.customer_id_a, data.customer_id_b)

    def _checklist(self, payload: ToolSchema) -> dict | None:
        data = self._as(payload, VerificationChecklistInput)
        return self.gateway.generate_verification_checklist(data.customer_id)

    def _event_detail(self, payload: ToolSchema) -> dict | None:
        data = self._as(payload, RiskEventDetailInput)
        return self.gateway.get_risk_event_detail(data.event_id)

    def _knowledge(self, payload: ToolSchema) -> dict:
        data = self._as(payload, RiskKnowledgeSearchInput)
        return self.gateway.search_risk_knowledge(data.query, data.category, data.limit)

    def _risk_evaluation_criteria(self, payload: ToolSchema) -> dict:
        self._as(payload, RiskEvaluationCriteriaInput)
        return self.gateway.get_risk_evaluation_criteria()

    def _transaction_risk(self, payload: ToolSchema) -> dict:
        data = self._as(payload, TransactionDecisionInput)
        return self.gateway.get_transaction_risk(data.transaction_context, data.customer_id, data.transaction_id)

    def _risk_exposure(self, payload: ToolSchema) -> dict:
        data = self._as(payload, TransactionDecisionInput)
        return self.gateway.calculate_risk_exposure(data.transaction_context, data.customer_id, data.transaction_id)

    def _evidence_completeness(self, payload: ToolSchema) -> dict:
        data = self._as(payload, TransactionDecisionInput)
        return self.gateway.get_evidence_completeness(data.transaction_context, data.customer_id, data.transaction_id)

    def _credit_terms(self, payload: ToolSchema) -> dict:
        data = self._as(payload, TransactionDecisionInput)
        return self.gateway.evaluate_credit_terms(data.transaction_context, data.customer_id, data.transaction_id)

    def _simulate_adjustment(self, payload: ToolSchema) -> dict:
        data = self._as(payload, TransactionSimulationInput)
        return self.gateway.simulate_transaction_adjustment(data.base_context, data.adjustments, data.customer_id, data.transaction_id)

    def _timeline(self, payload: ToolSchema) -> dict | None:
        data = self._as(payload, TransactionTimelineInput)
        return self.gateway.get_transaction_timeline(data.transaction_id)

    @staticmethod
    def _as(payload: ToolSchema, expected: type[ToolSchema]):
        """让类型收窄保持集中；运行时输入已由注册定义验证。"""

        if not isinstance(payload, expected):
            raise TypeError("Tool 输入类型与注册定义不一致")
        return payload

    @staticmethod
    def _validation_message(exc: ValidationError) -> str:
        errors = exc.errors(include_url=False)
        return "；".join(f"{'.'.join(map(str, item['loc']))}: {item['msg']}" for item in errors[:5])

    @staticmethod
    def _error(name: str, arguments: dict[str, Any], code: str, message: str) -> ToolResult:
        return ToolResult(
            tool=name,
            arguments=arguments,
            data={"success": False, "error": {"code": code, "message": message}},
            summary=f"工具调用失败：{message}",
            success=False,
            error_code=code,
            error_message=message,
        )

    @staticmethod
    def _summary(name: str, data: dict[str, Any]) -> str:
        templates = {
            "get_customer_profile": lambda: f"已读取 {data['company_name']} 的脱敏档案",
            "get_customer_credit_score": lambda: f"已读取保存的信用分 {data['total_score']:.1f}",
            "get_customer_transactions": lambda: f"共 {data['transaction_count']} 笔交易，返回最近 {len(data['recent_transactions'])} 笔",
            "get_order_risk_analysis": lambda: f"已完成订单 #{data['order_id']} 的只读风控分析",
            "list_risk_alerts": lambda: f"共 {data['total']} 条预警，返回 {len(data['items'])} 条",
            "compare_customers": lambda: "已完成两个外商的事实对比",
            "generate_verification_checklist": lambda: f"基于 {data['based_on_alert_count']} 条预警生成核验清单",
            "get_risk_event_detail": lambda: f"已读取风险事件 #{data['id']} 的证据快照",
            "search_risk_knowledge": lambda: f"通过 {data['retrieval_method']} 召回 {len(data['items'])} 条非结构化知识",
            "get_risk_evaluation_criteria": lambda: f"已读取 {data['transaction_risk']['version']} 的 {data['transaction_risk']['enabled_rule_count']} 条启用规则及完整决策口径",
            "get_transaction_risk": lambda: f"确定性交易风险等级为 {data['risk_level']}，命中 {len(data['triggered_rules'])} 条规则",
            "calculate_risk_exposure": lambda: f"预计最大风险敞口 {data['projected_max_exposure']:,.2f} {data['currency']}",
            "get_evidence_completeness": lambda: f"证据完整度 {data['completeness']:.0%}，缺少 {len(data['missing'])} 项",
            "evaluate_credit_terms": lambda: f"交易条件建议状态为 {data['decision_status']}",
            "simulate_transaction_adjustment": lambda: f"已完成条件模拟，预计敞口变化 {data['comparison']['projected_exposure_change']:,.2f}",
            "get_transaction_timeline": lambda: f"已读取交易 #{data['transaction_id']} 的 {len(data['items'])} 条时间线事件",
        }
        return templates[name]()

    @staticmethod
    def _metadata(name: str, data: dict[str, Any]) -> tuple[list[EvidenceRef], list[int], list[int], list[int]]:
        """仅生成来源引用与关联 ID，不做业务判断。"""

        if name == "get_customer_profile":
            customer_id = data["customer_id"]
            return [EvidenceRef("customer", str(customer_id), f"外商档案：{data['company_name']}")], [customer_id], [], []
        if name == "get_customer_credit_score":
            customer_id = data["customer_id"]
            return [EvidenceRef("credit_score", str(data["score_id"]), f"信用分 {data['total_score']:.1f}，{data['risk_level']}")], [customer_id], [], []
        if name == "get_customer_transactions":
            rows = data["recent_transactions"]
            evidence = [EvidenceRef("transaction", str(item["order_id"]), f"订单 {item['order_number']}，金额 {item['amount']}") for item in rows]
            return evidence, [data["customer_id"]], [item["order_id"] for item in rows], []
        if name == "get_order_risk_analysis":
            order_id = data["order_id"]
            evidence = [EvidenceRef("order_risk_analysis", str(order_id), f"只读风控结果：{data['risk_level']} / {data['overall_risk_score']:.1f}")]
            return evidence, [data["customer_id"]], [order_id], []
        if name in {"list_risk_alerts", "get_risk_event_detail"}:
            rows = data["items"] if name == "list_risk_alerts" else [data]
            evidence = [EvidenceRef("risk_event", str(item["id"]), f"{item['title']}：{item['risk_level']} / {item['risk_score']:.1f}") for item in rows]
            return evidence, sorted({item["customer_id"] for item in rows}), [item["order_id"] for item in rows if item.get("order_id")], [item["id"] for item in rows]
        if name == "compare_customers":
            rows = data["customers"]
            evidence = [EvidenceRef("customer_comparison", str(item["customer_id"]), f"对比数据：{item['company_name']}") for item in rows]
            return evidence, data["customer_ids"], [], []
        if name == "generate_verification_checklist":
            evidence = [EvidenceRef("customer", str(data["customer_id"]), f"核验对象：{data['company_name']}")]
            evidence.extend(EvidenceRef("risk_event", str(event_id), "人工核验清单依据") for event_id in data["risk_event_ids"])
            return evidence, [data["customer_id"]], [], data["risk_event_ids"]
        if name == "search_risk_knowledge":
            evidence = [
                EvidenceRef(
                    "knowledge_chunk",
                    str(item["knowledge_id"]),
                    f"{item['title']}（{item['category']}，相似度 {item['similarity']:.2f}）",
                )
                for item in data["items"]
            ]
            return evidence, [], [], []
        if name == "get_risk_evaluation_criteria":
            return [
                EvidenceRef(
                    "risk_methodology",
                    data["methodology_version"],
                    f"当前系统评价标准：{data['transaction_risk']['version']}，{data['transaction_risk']['enabled_rule_count']} 条启用规则",
                )
            ], [], [], []
        if name in {"get_transaction_risk", "calculate_risk_exposure", "get_evidence_completeness", "evaluate_credit_terms"}:
            transaction_id = data.get("transaction_id")
            if name == "evaluate_credit_terms":
                summary = f"交易决策：{data['decision_status']}，预计敞口 {data['risk_exposure']['projected_max_exposure']:.2f} {data['risk_exposure']['currency']}"
            elif name == "get_transaction_risk":
                summary = f"交易风险：{data['risk_level']} / {data['risk_score']:.1f}"
            elif name == "calculate_risk_exposure":
                summary = f"预计最大风险敞口：{data['projected_max_exposure']:.2f} {data['currency']}"
            else:
                summary = f"证据完整度：{data['completeness']:.0%}"
            return [EvidenceRef("transaction_decision", str(transaction_id or "draft"), summary)], [], [transaction_id] if transaction_id else [], []
        if name == "simulate_transaction_adjustment":
            return [EvidenceRef("decision_simulation", "draft", "交易条件调整前后确定性对比")], [], [], []
        if name == "get_transaction_timeline":
            return [EvidenceRef("transaction_timeline", str(data["transaction_id"]), f"{len(data['items'])} 条时间线事件")], [], [data["transaction_id"]], []
        return [], [], [], []


__all__ = [
    "AgentToolRegistry",
    "CustomerProfileInput",
    "CustomerProfileOutput",
    "CustomerCreditScoreInput",
    "CustomerCreditScoreOutput",
    "CustomerTransactionsInput",
    "CustomerTransactionsOutput",
    "OrderRiskAnalysisInput",
    "OrderRiskAnalysisOutput",
    "RiskAlertsInput",
    "RiskAlertsOutput",
    "CompareCustomersInput",
    "CompareCustomersOutput",
    "VerificationChecklistInput",
    "VerificationChecklistOutput",
    "RiskKnowledgeSearchInput",
    "RiskKnowledgeSearchOutput",
    "RiskEvaluationCriteriaInput",
    "RiskEvaluationCriteriaOutput",
    "TransactionDecisionInput",
    "TransactionRiskOutput",
    "RiskExposureOutput",
    "EvidenceCompletenessOutput",
    "TransactionDecisionOutput",
    "TransactionSimulationInput",
    "TransactionSimulationOutput",
    "TransactionTimelineInput",
    "TransactionTimelineOutput",
]
