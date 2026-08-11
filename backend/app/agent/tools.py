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
]
