RULES = [
    ("payment", ["货到付款", "收到货后付款", "payment after delivery"], "付款条款", "货到付款会放大回款风险", "改为30%预付款、70%发货前付清"),
    ("delivery", ["尽快交付", "as soon as possible", "另行通知"], "交付条款", "交付时间表述模糊", "写明最迟发货日和可接受的宽限期"),
    ("liability", ["全部责任", "all liability", "无限责任"], "责任转移", "卖方承担无限或不对等责任", "设置责任上限并排除间接损失"),
    ("refund", ["无条件退款", "unconditional refund"], "退款条款", "退款触发条件过于宽泛", "限定质量异议期限与第三方检验流程"),
    ("arbitration", ["买方所在地法院", "buyer jurisdiction"], "争议解决", "争议管辖对卖方明显不利", "采用双方认可的国际仲裁机构"),
    ("account", ["可随时变更收款账户", "change bank account anytime"], "账户安全", "允许单方变更收款账户", "账户变更须经双方授权人书面确认"),
]


def analyze_contract(text: str) -> dict:
    lower = text.lower()
    issues = []
    for code, words, category, explanation, suggestion in RULES:
        matches = [word for word in words if word.lower() in lower]
        if matches:
            issues.append({"code": code, "category": category, "matched": matches[0], "severity": "高" if code in {"payment", "liability", "account"} else "中", "explanation": explanation, "suggestion": suggestion})
    required = [("适用法律", ["适用法律", "governing law"]), ("知识产权", ["知识产权", "intellectual property"]), ("违约责任", ["违约", "breach"])]
    for category, words in required:
        if not any(word in lower for word in words):
            issues.append({"code": "missing", "category": category, "matched": "缺失条款", "severity": "中", "explanation": f"合同未明确{category}", "suggestion": f"补充清晰、对等的{category}条款"})
    high = sum(1 for item in issues if item["severity"] == "高")
    level = "高风险" if high >= 2 else "中风险" if issues else "低风险"
    return {
        "risk_level": level,
        "score": min(95, high * 25 + (len(issues) - high) * 10),
        "issues": issues,
        "safe_version": "建议安全框架：30%预付款；70%发货前付清；明确交货日期、验收标准与责任上限；争议提交双方认可的仲裁机构；任何账户变更须双重书面核验。",
        "disclaimer": "规则审核仅用于教学演示，不构成法律意见。",
    }

