def build_recommendations(risk_level: str, triggered_rules: list[dict]) -> list[str]:
    codes = {item["rule_code"] for item in triggered_rules}
    recommendations: list[str] = []
    if {"NEW_CUSTOMER_LARGE_ORDER", "PROFILE_CHANGE_LARGE_ORDER"} & codes:
        recommendations.append("进一步核实企业身份并要求补充注册及受益人材料")
    if {"PAYMENT_CHANGED", "COUNTRY_CHANGED", "ADDRESS_VOLATILITY"} & codes:
        recommendations.append("通过原有联系方式二次确认付款与收货信息")
    if {"AMOUNT_SURGE", "SMALL_TO_LARGE", "AMOUNT_ZSCORE", "SPLIT_ORDERS"} & codes:
        recommendations.append("提高定金比例并将订单转入人工复核")
    if "CONSECUTIVE_ADVERSE" in codes:
        recommendations.append("暂停赊账，待历史逾期、退款或纠纷结清后再继续")
    if risk_level == "critical":
        recommendations.extend(["建议暂停发货，完成增强尽调后再决定", "可加入观察名单；加入黑名单必须由授权人员确认"])
    elif risk_level == "high":
        recommendations.append("转人工审核并在发货前完成风险核验清单")
    elif risk_level == "medium":
        recommendations.append("保留常规交易流程，同时补充核验异常字段")
    else:
        recommendations.append("当前可按正常流程交易，并持续监控行为变化")
    return list(dict.fromkeys(recommendations))
