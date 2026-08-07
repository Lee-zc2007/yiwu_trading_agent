import re

from .schemas import ToolContext, ToolResult
from .tools import compare_customers, generate_verification_checklist, get_customer_credit_score, get_customer_profile, get_customer_transactions, get_risk_event_detail, list_risk_alerts


class MockAgent:
    def run(self, context: ToolContext, message: str, customer_id: int | None) -> tuple[str, list[ToolResult], bool]:
        text = message.lower(); calls: list[ToolResult] = []
        ids = [int(value) for value in re.findall(r"\b\d+\b", text)]
        if any(word in text for word in ["比较", "对比", "compare"]) and len(ids) >= 2:
            result = compare_customers(context, ids[0], ids[1]); calls.append(result)
            if len(result.data) < 2: return "至少有一个外商不存在，无法完成事实对比。", calls, True
            a, b = result.data
            answer = f"{a['profile']['company_name']} 信用分 {a['credit']['total_score']:.1f}，累计 {a['transaction_summary']['count']} 笔、金额 ${a['transaction_summary']['total_amount']:,.0f}；{b['profile']['company_name']} 信用分 {b['credit']['total_score']:.1f}，累计 {b['transaction_summary']['count']} 笔、金额 ${b['transaction_summary']['total_amount']:,.0f}。请结合置信度和风险事件进一步核验。"
            return answer, calls, False
        if any(word in text for word in ["核验", "清单", "checklist"]):
            if not customer_id: return "请先选择一个外商，我才能基于其真实档案生成核验清单。", calls, True
            result = generate_verification_checklist(context, customer_id); calls.append(result)
            return "建议按以下顺序核验：\n" + "\n".join(f"{index + 1}. {item}" for index, item in enumerate(result.data or [])), calls, not bool(result.data)
        if any(word in text for word in ["事件", "预警详情"]) and ids:
            result = get_risk_event_detail(context, ids[0]); calls.append(result)
            if not result.data: return "没有找到该风险事件。", calls, True
            rules = result.data.get("triggered_rules") or []
            return f"风险事件 #{result.data['id']} 得分 {result.data['risk_score']:.1f}，等级 {result.data['risk_level']}。主要证据：" + "；".join(rule["reason"] for rule in rules[:4]), calls, False
        if any(word in text for word in ["最近", "高风险", "预警"] ) and not customer_id:
            result = list_risk_alerts(context, limit=5); calls.append(result)
            if not result.data: return "当前没有风险预警。", calls, True
            return "最近优先关注：\n" + "\n".join(f"- 事件 #{item['id']}：{item['title']}，{item['risk_level']} / {item['risk_score']:.0f} 分" for item in result.data), calls, False
        if not customer_id:
            return "请先从右上角或外商页面选择具体外商；我不会在缺少客户上下文时猜测。", calls, True
        profile = get_customer_profile(context, customer_id); credit = get_customer_credit_score(context, customer_id); alerts = list_risk_alerts(context, customer_id, 5)
        calls.extend([profile, credit, alerts])
        if not profile.data or not credit.data: return "外商数据不足，无法给出可靠解释。", calls, True
        reasons = []
        for event in alerts.data:
            reasons.extend(rule.get("reason", "") for rule in event.get("triggered_rules", []) if rule.get("reason"))
        evidence_text = "；".join(list(dict.fromkeys(reasons))[:4]) or "当前没有已保存的规则命中证据"
        answer = f"{profile.data['company_name']} 当前信用分 {credit.data['total_score']:.1f}（{credit.data['risk_level']}，{credit.data['confidence_level']}）。证据显示：{evidence_text}。这些结果仅用于辅助判断，建议在采取暂停发货或黑名单措施前完成人工复核。"
        return answer, calls, False
