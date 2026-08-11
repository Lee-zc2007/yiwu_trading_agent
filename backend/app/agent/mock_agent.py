"""无需 LLM API Key 的确定性 Mock Agent。"""

from .schemas import AgentExecution, IntentResult, ToolResult
from .tools import AgentToolRegistry


class MockAgent:
    """按意图调用白名单工具，保证断网环境也能完成完整路演。"""

    def __init__(self, tools: AgentToolRegistry):
        self.tools = tools

    def run(self, message: str, customer_id: int | None, intent: IntentResult) -> AgentExecution:
        calls: list[ToolResult] = []

        if intent.name == "knowledge_search":
            result = self.tools.execute("search_risk_knowledge", {"query": message, "limit": 5})
            calls.append(result)
            items = result.data.get("items", []) if result.success else []
            if not items:
                return AgentExecution("风控知识库中没有召回足够相关的内容。", calls, True, "mock")
            answer = "非结构化知识（RAG）检索结果：\n" + "\n".join(
                f"- {item['title']}：{item['content']}" for item in items[:5]
            )
            answer += "\n以上是通用经验，不代表当前客户已经发生相同事实。"
            return AgentExecution(answer, calls, False, "mock")

        if intent.name == "compare_customers" and len(intent.entity_ids) >= 2:
            result = self.tools.execute("compare_customers", {"customer_id_a": intent.entity_ids[0], "customer_id_b": intent.entity_ids[1]})
            calls.append(result)
            compared = result.data.get("customers", []) if result.success else []
            if len(compared) < 2:
                return AgentExecution("至少有一个外商不存在，无法完成事实对比。", calls, True, "mock")
            first, second = compared
            if first.get("credit_score") is None or second.get("credit_score") is None:
                return AgentExecution("至少有一个外商没有已保存的信用评分，暂时无法进行可靠对比。", calls, True, "mock")
            answer = (
                f"{first['company_name']} 已保存信用分 {first['credit_score']:.1f}，"
                f"累计 {first['transaction_count']} 笔、金额 ${first['total_transaction_amount']:,.0f}；"
                f"{second['company_name']} 已保存信用分 {second['credit_score']:.1f}，"
                f"累计 {second['transaction_count']} 笔、金额 ${second['total_transaction_amount']:,.0f}。"
                "以上是已有业务数据对比，不构成最终交易决策。"
            )
            return AgentExecution(answer, calls, False, "mock")

        if intent.name == "verification_checklist":
            if not customer_id:
                return AgentExecution("请先选择一个外商，我才能基于其既有风险事件生成核验清单。", calls, True, "mock")
            result = self.tools.execute("generate_verification_checklist", {"customer_id": customer_id})
            knowledge = self.tools.execute("search_risk_knowledge", {"query": f"{message} 高风险订单人工复核操作规范", "limit": 3})
            calls.extend([result, knowledge])
            items = result.data.get("items", []) if result.success else []
            answer = "建议按以下顺序核验：\n" + "\n".join(f"{index + 1}. {item['item']}" for index, item in enumerate(items))
            references = knowledge.data.get("items", []) if knowledge.success else []
            if references:
                answer += "\n\n非结构化知识参考（RAG）：\n" + "\n".join(
                    f"- {item['title']}：{item['content']}" for item in references[:2]
                )
            return AgentExecution(answer, calls, not bool(items), "mock")

        if intent.name == "risk_event_detail" and intent.entity_ids:
            result = self.tools.execute("get_risk_event_detail", {"event_id": intent.entity_ids[0]})
            calls.append(result)
            if not result.success:
                return AgentExecution("没有找到该风险事件。", calls, True, "mock")
            rules = result.data.get("triggered_rules") or []
            reasons = "；".join(rule.get("reason", "") for rule in rules[:4] if rule.get("reason")) or "该事件没有明确规则命中，请查看保存的模型证据"
            answer = f"风险事件 #{result.data['id']} 的已保存风险分为 {result.data['risk_score']:.1f}，等级为 {result.data['risk_level']}。主要证据：{reasons}。"
            return AgentExecution(answer, calls, False, "mock")

        if intent.name == "recent_alerts":
            result = self.tools.execute("list_risk_alerts", {"limit": 5})
            calls.append(result)
            items = result.data.get("items", []) if result.success else []
            if not items:
                return AgentExecution("当前没有已保存的风险预警。", calls, True, "mock")
            answer = "最近优先关注：\n" + "\n".join(
                f"- 事件 #{item['id']}：{item['title']}，{item['risk_level']} / {item['risk_score']:.0f} 分"
                for item in items
            )
            return AgentExecution(answer, calls, False, "mock")

        if intent.name == "transaction_history":
            if not customer_id:
                return AgentExecution("请先选择外商，再查询其交易历史。", calls, True, "mock")
            result = self.tools.execute("get_customer_transactions", {"customer_id": customer_id, "limit": 10})
            calls.append(result)
            if not result.success or result.data["transaction_count"] == 0:
                return AgentExecution("该外商暂无可用交易记录。", calls, True, "mock")
            answer = (
                f"该外商共有 {result.data['transaction_count']} 笔交易，历史累计金额 "
                f"${result.data['total_transaction_amount']:,.2f}，平均订单金额 "
                f"${result.data['average_order_amount']:,.2f}。最近交易可在右侧证据区查看。"
            )
            return AgentExecution(answer, calls, False, "mock")

        if intent.name == "customer_profile":
            target = customer_id or (intent.entity_ids[0] if intent.entity_ids else None)
            if not target:
                return AgentExecution("请指定要查询的外商。", calls, True, "mock")
            result = self.tools.execute("get_customer_profile", {"customer_id": target})
            calls.append(result)
            if not result.success:
                return AgentExecution("没有找到该外商档案。", calls, True, "mock")
            answer = f"{result.data['company_name']} 位于 {result.data['country']}，主营品类为 {result.data.get('main_product_category') or '未填写'}，身份核验状态为{'已核验' if result.data.get('identity_verified') else '未核验'}。"
            return AgentExecution(answer, calls, False, "mock")

        if not customer_id:
            return AgentExecution("请先选择具体外商，或输入“最近高风险预警”“比较客户 5 和 7”等问题。", calls, True, "mock")

        # 默认风险解释严格读取档案、最新已保存评分和风险事件，不触发任何计算。
        profile = self.tools.execute("get_customer_profile", {"customer_id": customer_id})
        credit = self.tools.execute("get_customer_credit_score", {"customer_id": customer_id})
        alerts = self.tools.execute("list_risk_alerts", {"customer_id": customer_id, "limit": 5})
        knowledge = self.tools.execute("search_risk_knowledge", {"query": message, "limit": 3})
        calls.extend([profile, credit, alerts, knowledge])
        if not profile.success or not credit.success:
            return AgentExecution("外商档案或已保存信用评分不足。请先在业务流程中完成风控分析，Agent 不会自行计算评分。", calls, True, "mock")
        reasons = []
        alert_items = alerts.data.get("items", []) if alerts.success else []
        for event in alert_items:
            reasons.extend(rule.get("reason", "") for rule in event.get("triggered_rules", []) if rule.get("reason"))
        evidence_text = "；".join(list(dict.fromkeys(reasons))[:4]) or "当前没有已保存的规则命中证据"
        answer = (
            f"结构化业务事实（SQL 服务）：{profile.data['company_name']} 当前已保存信用分为 {credit.data['total_score']:.1f}"
            f"（{credit.data['risk_level']}，{credit.data['confidence_level']}）。证据显示：{evidence_text}。"
            "这些结果仅用于辅助判断，暂停发货或加入黑名单前必须人工复核。"
        )
        references = knowledge.data.get("items", []) if knowledge.success else []
        if references:
            answer += "\n\n非结构化知识参考（RAG，不是当前客户事实）：\n" + "\n".join(
                f"- {item['title']}：{item['content']}" for item in references[:2]
            )
        return AgentExecution(answer, calls, False, "mock")
