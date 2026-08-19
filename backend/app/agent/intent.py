"""Agent 意图识别。

基础框架使用确定性关键词路由，保证没有 LLM Key 时也能稳定演示。未来可替换为
模型分类器，但分类结果只能决定调用哪个只读工具，不能决定风险分或风险等级。
"""

import re

from .schemas import IntentResult


class IntentRecognizer:
    """识别当前问题希望查询的业务能力。"""

    def recognize(self, message: str, customer_id: int | None) -> IntentResult:
        text = message.lower().strip()
        ids = [int(value) for value in re.findall(r"\b\d+\b", text)]
        order_ids = [int(value) for value in re.findall(r"(?:订单|order)\s*#?\s*(\d+)", text)]

        term_words = ["定金", "账期", "付款节点", "分批发货", "分批付款", "交易条件"]
        if any(word in text for word in ["如果", "假如", "改成", "提高到", "缩短到", "延长到"]) and any(word in text for word in term_words):
            return IntentResult("modify_transaction_terms", 0.99, order_ids[:1])
        decision_request = any(phrase in text for phrase in [
            "第一次合作", "首次合作", "这笔订单账能放吗", "能不能放账", "可以放账吗",
            "授信条件", "交易授信", "风险敞口", "预计敞口", "准备做", "希望给",
            "还缺哪些关键信息", "缺什么信息", "缺哪些材料",
        ])
        decision_request = decision_request or (
            any(word in text for word in ["订单", "交易", "客户"]) and any(word in text for word in term_words)
        )
        if decision_request:
            return IntentResult("transaction_decision", 0.97, order_ids[:1])
        if any(word in text for word in ["比较", "对比", "compare"]) and len(ids) >= 2:
            return IntentResult("compare_customers", 0.98, ids[:2])
        if any(word in text for word in ["核验", "清单", "checklist", "尽调", "调查建议", "调查"]):
            return IntentResult("verification_checklist", 0.96, [customer_id] if customer_id else [])
        methodology_request = any(phrase in text for phrase in [
            "评价标准", "评估标准", "风险标准", "评分标准", "评分规则", "评价体系", "评估体系",
            "风险口径", "风险规则有哪些", "系统怎么评价", "系统如何评价", "怎么判断客户风险", "如何判断客户风险",
        ])
        if methodology_request:
            return IntentResult("risk_methodology", 0.99)
        if any(word in text for word in ["信用", "信用分", "评分", "credit"]):
            return IntentResult("credit_status", 0.96, [customer_id] if customer_id else ids[:1])
        knowledge_request = any(phrase in text for phrase in [
            "风险案例", "义乌市场", "市场经验", "合同风险", "合同条款", "贸易合同",
            "操作规范", "风控规范", "风控知识", "知识库", "sop", "rag",
        ])
        risk_request = any(word in text for word in ["订单风险", "风险分析", "分析风险", "为什么有风险", "为什么风险高", "risk analysis"])
        risk_request = risk_request or ("风险" in text and any(word in text for word in ["订单", "分析", "为什么"]))
        # 明确选择了客户/订单时可同时执行结构化风控查询和 RAG；纯案例、合同、
        # 规范问题只走知识库，不把它误路由成交易查询。
        if risk_request and (customer_id or order_ids or not knowledge_request):
            # 明确写在问题中的数字按订单候选 ID 交给图路由；如果只有客户上下文，
            # 图会先通过交易 Tool 解析最近订单，不会直接查询数据库。
            return IntentResult("risk_analysis", 0.95, order_ids[:1])
        if knowledge_request:
            return IntentResult("knowledge_search", 0.94)
        if any(word in text for word in ["事件", "预警详情"]) and ids:
            return IntentResult("risk_event_detail", 0.95, ids[:1])
        if any(word in text for word in ["交易", "订单历史", "采购历史", "transactions"]):
            return IntentResult("transaction_history", 0.90, [customer_id] if customer_id else [])
        if any(phrase in text for phrase in ["最近高风险客户", "最近高风险预警", "查看最近高风险"]):
            return IntentResult("recent_alerts", 0.96)
        if any(word in text for word in ["最近", "高风险", "预警", "alerts"]) and not customer_id:
            return IntentResult("recent_alerts", 0.92)
        if any(word in text for word in ["档案", "资料", "客户信息", "profile"]):
            return IntentResult("customer_profile", 0.88, [customer_id] if customer_id else ids[:1])
        if customer_id:
            return IntentResult("risk_explanation", 0.85, [customer_id])
        return IntentResult("unknown", 0.40, ids)
