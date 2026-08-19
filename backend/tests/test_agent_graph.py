"""Agent 决策图意图、工具路由、状态快照和证据约束测试。"""

import json

import httpx
import pytest

from backend.app.agent.graph import AgentDecisionGraph, graph_status
from backend.app.agent.schemas import ToolResult
from backend.app.agent.service import AgentService
from backend.app.core.config import settings
from backend.app.agent.tools import AgentToolRegistry
from backend.app.core.database import SessionLocal
from backend.app.services.agent_data import SqlAlchemyAgentDataGateway


@pytest.mark.parametrize(
    ("message", "customer_id", "expected_intent", "expected_tool"),
    [
        ("查询客户信息", 5, "customer_profile", "get_customer_profile"),
        ("查询信用情况", 5, "credit_status", "get_customer_credit_score"),
        ("为什么这个客户风险高", 5, "risk_analysis", "get_order_risk_analysis"),
        ("比较客户 5 和 6", None, "compare_customers", "compare_customers"),
        ("生成调查建议", 5, "verification_checklist", "generate_verification_checklist"),
    ],
)
def test_graph_routes_five_core_intents_and_cites_evidence(client, message, customer_id, expected_intent, expected_tool):
    with SessionLocal() as db:
        graph = AgentDecisionGraph(AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1)))
        execution = graph.run(message, customer_id)

    assert execution.intent == expected_intent
    assert expected_tool in [item.tool for item in execution.tool_results]
    assert execution.insufficient_data is False
    assert "根据系统" in execution.answer
    assert "证据来源" in execution.answer
    assert execution.call_chain[0]["node"] == "START"
    assert execution.call_chain[-1]["node"] == "END"
    assert len(execution.state_history) == len(execution.call_chain)
    for snapshot in execution.state_history:
        assert {
            "message",
            "customer_id",
            "intent",
            "tool_calls",
            "tool_results",
            "evidence",
            "final_answer",
        }.issubset(snapshot)


def test_risk_answer_uses_exact_tool_result_instead_of_experience(client):
    with SessionLocal() as db:
        graph = AgentDecisionGraph(AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1)))
        execution = graph.run("分析这个客户为什么风险高", 5)

    risk_result = next(item.data for item in execution.tool_results if item.tool == "get_order_risk_analysis")
    assert risk_result["risk_level"] in execution.answer
    assert f"{risk_result['overall_risk_score']:.1f}" in execution.answer
    assert f"{risk_result['credit_score']:.1f}" in execution.answer
    assert risk_result["abnormal_reasons"][0] in execution.answer
    assert "根据经验" not in execution.answer


def test_graph_returns_data_insufficient_without_tool_evidence(client):
    with SessionLocal() as db:
        graph = AgentDecisionGraph(AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1)))
        execution = graph.run("你好，请随便判断一下", None)

    assert execution.insufficient_data is True
    assert execution.tool_results == []
    assert execution.answer.startswith("数据不足")


def test_risk_graph_requires_target_risk_tool_not_only_order_resolution(client):
    """前置交易查询成功不能冒充订单风险分析成功。"""

    with SessionLocal() as db:
        tools = AgentToolRegistry(SqlAlchemyAgentDataGateway(db, merchant_id=1))
        original_execute = tools.execute

        def fail_risk_tool(name, arguments=None):
            if name == "get_order_risk_analysis":
                return ToolResult(
                    tool=name,
                    arguments=arguments or {},
                    data={"success": False, "error": {"code": "BUSINESS_DATA_NOT_FOUND", "message": "没有已有评分"}},
                    summary="工具调用失败：没有已有评分",
                    success=False,
                    error_code="BUSINESS_DATA_NOT_FOUND",
                    error_message="没有已有评分",
                )
            return original_execute(name, arguments)

        tools.execute = fail_risk_tool
        execution = AgentDecisionGraph(tools).run("为什么这个客户风险高", 5)

    assert execution.insufficient_data is True
    assert execution.answer.startswith("数据不足")
    assert "没有已有评分" in execution.answer


def test_graph_exposes_langgraph_compatible_runtime_status():
    status = graph_status()
    assert status["enabled"] is True
    assert status["backend"] == "simple_state_machine"
    assert status["nodes"][0] == "START"
    assert status["nodes"][-1] == "END"


def test_llm_mode_reuses_tool_results_to_return_graph_trace(client, monkeypatch):
    class FakeProvider:
        provider_name = "fake"

        def complete(self, messages, tools=None):
            if tools:
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call-credit",
                        "type": "function",
                        "function": {"name": "get_customer_credit_score", "arguments": '{"customer_id": 5}'},
                    }],
                }
            tool_message = next(item for item in reversed(messages) if item.get("role") == "tool")
            tool_payload = json.loads(tool_message["content"])
            score = tool_payload["data"]["total_score"]
            return {"role": "assistant", "content": f"根据系统信用评分工具，该客户信用分为 {score:.1f} 分。"}

    monkeypatch.setattr(settings, "agent_mode", "llm")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    with SessionLocal() as db:
        response = AgentService(
            SqlAlchemyAgentDataGateway(db, merchant_id=1),
            merchant_id=1,
            provider=FakeProvider(),
        ).chat("查询信用情况", 5, "pytest-llm-graph")

    assert response.mode == "llm:fake"
    assert response.tools_used == ["get_customer_credit_score"]
    assert response.call_chain[0].node == "START"
    assert response.call_chain[-1].node == "END"
    assert len(response.state_history) == len(response.call_chain)
    assert "信用分为" in response.answer


def test_llm_failure_is_reported_without_mock_answer(client, monkeypatch):
    class TimeoutProvider:
        provider_name = "deepseek"

        def complete(self, messages, tools=None):
            raise httpx.ReadTimeout("test timeout")

    monkeypatch.setattr(settings, "agent_mode", "llm")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    with SessionLocal() as db:
        response = AgentService(
            SqlAlchemyAgentDataGateway(db, merchant_id=1),
            merchant_id=1,
            provider=TimeoutProvider(),
        ).chat("查询信用情况", 5, "pytest-llm-timeout")

    assert response.mode == "llm-error:timeout"
    assert response.insufficient_data is True
    assert "没有生成本地替代回答" in response.answer
    assert "Mock Agent" not in response.answer


def test_llm_without_tool_call_is_retried_then_rejected(client, monkeypatch):
    class NoToolProvider:
        provider_name = "deepseek"

        def __init__(self):
            self.calls = 0

        def complete(self, messages, tools=None):
            self.calls += 1
            return {"role": "assistant", "content": "我直接回答。"}

    provider = NoToolProvider()
    monkeypatch.setattr(settings, "agent_mode", "llm")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    with SessionLocal() as db:
        response = AgentService(
            SqlAlchemyAgentDataGateway(db, merchant_id=1),
            merchant_id=1,
            provider=provider,
        ).chat("查询信用情况", 5, "pytest-llm-no-tool")

    assert provider.calls == 2
    assert response.mode == "llm-error:no-tool"
    assert response.insufficient_data is True
    assert response.tools_used == []
    assert "没有生成本地替代回答" in response.answer


def test_llm_internal_tool_markup_is_corrected_before_return(client, monkeypatch):
    class MarkupProvider:
        provider_name = "deepseek"

        def __init__(self):
            self.calls = 0

        def complete(self, messages, tools=None):
            self.calls += 1
            if tools:
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call-credit-markup",
                        "type": "function",
                        "function": {"name": "get_customer_credit_score", "arguments": '{"customer_id": 5}'},
                    }],
                }
            if self.calls == 2:
                return {"role": "assistant", "content": '<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name="unknown">'}
            return {"role": "assistant", "content": "根据已返回的信用评分证据，该客户信用情况已完成核验。"}

    provider = MarkupProvider()
    monkeypatch.setattr(settings, "agent_mode", "llm")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    with SessionLocal() as db:
        response = AgentService(
            SqlAlchemyAgentDataGateway(db, merchant_id=1),
            merchant_id=1,
            provider=provider,
        ).chat("查询信用情况", 5, "pytest-llm-markup")

    assert provider.calls == 3
    assert response.mode == "llm:deepseek"
    assert response.tools_used == ["get_customer_credit_score"]
    assert "DSML" not in response.answer
    assert "完成核验" in response.answer


def test_transaction_decision_answer_is_also_generated_by_llm(client, monkeypatch):
    class DecisionProvider:
        provider_name = "deepseek"

        def complete(self, messages, tools=None):
            assert tools is None
            assert any("确定性状态机" in str(item.get("content") or "") for item in messages)
            return {
                "role": "assistant",
                "content": "我已通过受控风控流程记录订单条件。请补充这笔订单计划支付的定金比例。",
            }

    monkeypatch.setattr(settings, "agent_mode", "llm")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    with SessionLocal() as db:
        response = AgentService(
            SqlAlchemyAgentDataGateway(db, merchant_id=1),
            merchant_id=1,
            provider=DecisionProvider(),
        ).chat(
            "一个迪拜客户第一次合作，准备做3万美元订单，希望给45天账期。",
            None,
            "pytest-llm-decision",
        )

    assert response.mode == "llm:deepseek"
    assert response.intent == "transaction_decision"
    assert "deposit_ratio" in response.missing_fields
    assert "定金比例" in response.answer
    response_generation = next(item for item in response.call_chain if item.node == "Response Generation")
    assert response_generation.detail["source"] == "deepseek_from_deterministic_tools"
    assert response.state_history[-1].final_answer == response.answer
