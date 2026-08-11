"""Agent Tool 契约、异常封装和只读边界测试。"""

import json

from backend.app.agent.tools import AgentToolRegistry
from backend.app.core.database import SessionLocal
from backend.app.models import CreditScoreHistory, RiskEvent, Transaction
from backend.app.services.agent_data import SqlAlchemyAgentDataGateway


def test_all_core_agent_tools_return_schema_valid_json(client):
    """核心 Tool 均应返回可直接交给 LLM 的结构化 JSON。"""

    with SessionLocal() as db:
        order_id = (
            db.query(Transaction.id)
            .filter(Transaction.merchant_id == 1, Transaction.customer_id == 5)
            .order_by(Transaction.order_time.desc())
            .first()
        )[0]
        tools = AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1))
        calls = [
            ("get_customer_profile", {"customer_id": 5}),
            ("get_customer_credit_score", {"customer_id": 5}),
            ("get_customer_transactions", {"customer_id": 5, "limit": 3}),
            ("get_order_risk_analysis", {"order_id": order_id}),
            ("list_risk_alerts", {"customer_id": 5, "limit": 3}),
            ("compare_customers", {"customer_id_a": 5, "customer_id_b": 6}),
            ("generate_verification_checklist", {"customer_id": 5}),
            ("search_risk_knowledge", {"query": "义乌市场付款账户变更怎么核验", "limit": 3}),
        ]

        for name, arguments in calls:
            result = tools.execute(name, arguments)
            assert result.success, (name, result.error_code, result.error_message)
            assert isinstance(result.data, dict)
            assert json.loads(json.dumps(result.data, ensure_ascii=False)) == result.data

        transactions = tools.execute("get_customer_transactions", {"customer_id": 5, "limit": 3}).data
        assert transactions["transaction_count"] == 15
        assert len(transactions["recent_transactions"]) == 3
        assert transactions["average_order_amount"] > 0


def test_agent_tool_rejects_invalid_or_unlisted_calls(client):
    with SessionLocal() as db:
        tools = AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1))

        invalid = tools.execute("get_customer_profile", {"customer_id": 0, "unexpected": True})
        assert invalid.success is False
        assert invalid.error_code == "TOOL_INPUT_INVALID"
        assert invalid.data["error"]["code"] == "TOOL_INPUT_INVALID"

        same_customer = tools.execute("compare_customers", {"customer_id_a": 5, "customer_id_b": 5})
        assert same_customer.success is False
        assert same_customer.error_code == "TOOL_INPUT_INVALID"

        unknown = tools.execute("run_sql", {"sql": "SELECT * FROM customers"})
        assert unknown.success is False
        assert unknown.error_code == "TOOL_NOT_ALLOWED"


def test_order_risk_tool_does_not_persist_event_or_credit_score(client):
    """订单 Tool 可调用现有风控能力，但不能新增预警或信用评分记录。"""

    with SessionLocal() as db:
        order_id = (
            db.query(Transaction.id)
            .filter(Transaction.merchant_id == 1, Transaction.customer_id == 5)
            .order_by(Transaction.order_time.desc())
            .first()
        )[0]
        event_count_before = db.query(RiskEvent).count()
        credit_count_before = db.query(CreditScoreHistory).count()

        result = AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1)).execute(
            "get_order_risk_analysis",
            {"order_id": order_id},
        )

        assert result.success
        assert result.data["analysis_source"] == "runtime_read_only"
        assert result.data["risk_event_id"] is None
        assert db.query(RiskEvent).count() == event_count_before
        assert db.query(CreditScoreHistory).count() == credit_count_before


def test_tool_calling_specs_are_generated_from_strict_input_schemas(client):
    with SessionLocal() as db:
        tools = AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1))
        specs = {item["function"]["name"]: item["function"] for item in tools.llm_specs()}

        for name in {
            "get_customer_profile",
            "get_customer_credit_score",
            "get_customer_transactions",
            "get_order_risk_analysis",
            "list_risk_alerts",
            "compare_customers",
            "generate_verification_checklist",
            "search_risk_knowledge",
        }:
            assert name in specs
            assert specs[name]["description"]
            assert specs[name]["parameters"]["additionalProperties"] is False
