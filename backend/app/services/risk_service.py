def level_for(score: int) -> str:
    if score < 30:
        return "低风险"
    if score < 60:
        return "中风险"
    if score < 80:
        return "高风险"
    return "极高风险"


def evaluate_risk(data: dict) -> dict:
    factors: list[dict] = []

    def add(name: str, score: int, reason: str):
        factors.append({"name": name, "contribution": score, "reason": reason})

    years = data["registered_years"]
    add("注册年限", 12 if years == 0 else 7 if years < 2 else 2 if years < 5 else 0, f"企业注册 {years} 年")
    complete = data["profile_completeness"]
    add("资料完整度", round((100 - complete) * 0.12), f"资料完整度 {complete}%")
    history = data["historical_orders"]
    add("历史成交", 10 if history == 0 else 5 if history < 3 else 0, f"历史订单 {history} 笔")
    disputes = data["disputes"]
    add("历史纠纷", min(15, disputes * 6), f"历史纠纷 {disputes} 次")
    payment = data["payment_method"].lower()
    risky_payment = any(word in payment for word in ["cod", "货到付款", "crypto", "加密", "personal"])
    add("付款方式", 18 if risky_payment else 3 if "l/c" not in payment and "t/t" not in payment else 0, f"付款方式：{data['payment_method']}")
    amount = data["order_amount"]
    add("金额异常", 9 if history == 0 and amount > 50_000 else 4 if amount > 100_000 else 0, f"订单金额 ${amount:,.0f}")
    add("地址完整度", 0 if data["address_complete"] else 8, "收货地址完整" if data["address_complete"] else "收货地址缺失")
    add("邮箱域名", 0 if data["corporate_email"] else 7, "企业邮箱" if data["corporate_email"] else "免费公共邮箱")
    changes = data["account_changes"]
    add("账户变更", min(12, changes * 5), f"收款账户变更 {changes} 次")
    add("身份验证", 14 if data["verification_refused"] else 0, "拒绝视频或身份验证" if data["verification_refused"] else "愿意配合验证")
    add("异常紧迫性", 7 if data["urgent_language"] else 0, "语言存在异常催促" if data["urgent_language"] else "沟通节奏正常")
    add("行为一致性", 0 if data["behavior_consistent"] else 10, "行为前后一致" if data["behavior_consistent"] else "需求与身份信息不一致")
    score = min(100, sum(item["contribution"] for item in factors))
    level = level_for(score)
    continue_trade = score < 80
    deposit = 30 if score < 30 else 50 if score < 60 else 80 if score < 80 else 100
    return {
        "score": score,
        "level": level,
        "factors": factors,
        "top_reasons": [item["reason"] for item in sorted(factors, key=lambda item: item["contribution"], reverse=True)[:4] if item["contribution"]],
        "recommendation": "可按常规流程推进，并保留贸易凭证。" if score < 30 else "补充工商资料与视频验证，采用分阶段付款。" if score < 60 else "仅在强化尽调与高比例预付款后推进。" if score < 80 else "建议暂停交易并进行独立人工核验。",
        "payment_recommendation": "T/T 或不可撤销信用证",
        "recommended_deposit_percent": deposit,
        "continue_trade": continue_trade,
        "mitigations": ["核验公司注册资料", "进行视频身份验证", "收款账户二次确认", "购买出口信用保险"],
        "disclaimer": "该风险评分为教学和演示模型，不构成真实征信或商业决策依据。",
    }

