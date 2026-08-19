"""Agent 内部使用的数据契约。

本模块只定义 Python 协议和轻量数据对象，不导入 SQLAlchemy，也不持有数据库
Session。这样可以从类型层面保证 Agent、确定性状态机和 LLM Provider 都不能直接
访问数据库；真实业务数据只能经由 ``AgentDataGateway`` 提供。
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


class AgentDataGateway(Protocol):
    """Agent 可见的只读业务数据接口。

    具体实现放在 ``backend.app.services`` 中。未来无论数据来自本地服务、内部
    HTTP API 还是其他微服务，Agent 侧都不需要知道数据库细节。
    """

    def get_customer_profile(self, customer_id: int | None = None, query: str = "") -> dict | None: ...

    def get_latest_credit_score(self, customer_id: int) -> dict | None: ...

    def get_customer_transactions(self, customer_id: int, limit: int = 10) -> dict | None: ...

    def analyze_order_risk(self, order_id: int) -> dict | None: ...

    def list_risk_alerts(self, customer_id: int | None = None, limit: int = 10) -> dict: ...

    def compare_customers(self, customer_id_a: int, customer_id_b: int) -> dict | None: ...

    def generate_verification_checklist(self, customer_id: int) -> dict | None: ...

    def get_risk_event_detail(self, event_id: int) -> dict | None: ...

    def search_risk_knowledge(self, query: str, category: str | None = None, limit: int = 5) -> dict: ...

    def get_risk_evaluation_criteria(self) -> dict: ...

    def evaluate_transaction_decision(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict: ...

    def get_transaction_risk(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict: ...

    def calculate_risk_exposure(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict: ...

    def get_evidence_completeness(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict: ...

    def evaluate_credit_terms(self, transaction_context: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict: ...

    def simulate_transaction_adjustment(self, base_context: dict, adjustments: dict, customer_id: int | None = None, transaction_id: int | None = None) -> dict: ...

    def get_transaction_timeline(self, transaction_id: int) -> dict | None: ...


class DecisionContextStore(Protocol):
    """结构化决策上下文接口；实现位于 Service 层，Agent 不感知数据库。"""

    def load(self, merchant_id: int, conversation_id: str) -> dict[str, Any]: ...

    def save(self, merchant_id: int, conversation_id: str, **state: Any) -> dict[str, Any]: ...


@dataclass(slots=True)
class EvidenceRef:
    """一条可回溯的业务证据引用，不复制完整敏感数据。"""

    source_type: str
    source_id: str
    summary: str


@dataclass(slots=True)
class ToolResult:
    """白名单工具的统一返回结构。"""

    tool: str
    arguments: dict[str, Any]
    data: Any
    summary: str
    evidence: list[EvidenceRef] = field(default_factory=list)
    customer_ids: list[int] = field(default_factory=list)
    order_ids: list[int] = field(default_factory=list)
    event_ids: list[int] = field(default_factory=list)
    success: bool = True
    error_code: str | None = None
    error_message: str | None = None


@dataclass(slots=True)
class IntentResult:
    """轻量意图识别结果，用于 Mock 演示及 LLM 路由提示。"""

    name: str
    confidence: float
    entity_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class AgentExecution:
    """确定性状态机与 LLM Agent 共同遵守的执行结果。"""

    answer: str
    tool_results: list[ToolResult]
    insufficient_data: bool
    mode: str
    intent: str = ""
    call_chain: list[dict[str, Any]] = field(default_factory=list)
    state_history: list[dict[str, Any]] = field(default_factory=list)
    transaction_id: int | None = None
    context_version: int = 1
    transaction_context: dict[str, Any] = field(default_factory=dict)
    required_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    information_completeness: float = 0
    next_best_question: str = ""
    decision_result: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
