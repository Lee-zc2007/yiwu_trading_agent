def calculate_impact(data: dict) -> dict:
    inquiries = data["daily_inquiries"]
    automation = data["ai_automation_rate"] / 100
    manual_minutes = data["manual_reply_minutes"] + data["manual_quote_minutes"] * 0.35
    saved_hours_day = inquiries * manual_minutes * automation / 60
    monthly_cost = saved_hours_day * 22 * data["hourly_cost"]
    response_drop = max(0, (data["manual_reply_minutes"] - 8 / 60) / max(data["manual_reply_minutes"], 0.01) * 100)
    quote_efficiency = max(0, (data["manual_quote_minutes"] - 0.5) / max(data["manual_quote_minutes"], 0.01) * 100)
    filtered_fake = inquiries * data["fake_inquiry_rate"] / 100 * automation
    added_valid = inquiries * 22 * automation * 0.08
    conversion_lift = min(4.5, automation * 3.8)
    added_revenue = added_valid * (data["conversion_rate"] + conversion_lift) / 100 * data["average_order_amount"]
    avoided_loss = inquiries * 22 * data["fake_inquiry_rate"] / 100 * 0.025 * data["average_order_amount"] * automation
    assumed_monthly_cost = 2800
    roi = (monthly_cost + added_revenue * 0.12 + avoided_loss - assumed_monthly_cost) / assumed_monthly_cost * 100
    return {
        "saved_hours_day": round(saved_hours_day, 1),
        "monthly_labor_saving": round(monthly_cost, 0),
        "response_time_drop_percent": round(response_drop, 1),
        "quote_efficiency_gain_percent": round(quote_efficiency, 1),
        "fake_inquiries_filtered_day": round(filtered_fake, 1),
        "new_valid_inquiries_month": round(added_valid, 0),
        "conversion_lift_points": round(conversion_lift, 1),
        "new_revenue_month": round(added_revenue, 0),
        "avoided_risk_loss_month": round(avoided_loss, 0),
        "roi_percent": round(roi, 0),
        "assumptions": ["每月按22个工作日", "AI带来8%的有效询盘增量假设", "新增成交额按12%贡献毛利", "系统月成本假设为¥2,800"],
        "disclaimer": "以上均为基于调研假设的 Demo 模拟估算，不代表真实经营结果。",
    }

