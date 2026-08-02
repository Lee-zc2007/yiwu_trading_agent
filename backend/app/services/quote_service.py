from datetime import date, timedelta


def calculate_quote(payload: dict) -> dict:
    quantity = payload["quantity"]
    subtotal = payload["unit_price"] * quantity
    discounted = subtotal * (1 - payload["discount"] / 100)
    tax = discounted * payload["tax_rate"] / 100
    extras = payload["packaging_fee"] + payload["freight"] + payload["insurance"] + tax
    total_amount = discounted + extras
    total_cost = payload["unit_cost"] * quantity + payload["packaging_fee"] + payload["freight"] + payload["insurance"]
    expected_profit = total_amount - total_cost
    margin_rate = expected_profit / total_amount * 100 if total_amount else 0
    return {
        **payload,
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "total_cost": round(total_cost, 2),
        "total_amount": round(total_amount, 2),
        "expected_profit": round(expected_profit, 2),
        "margin_rate": round(margin_rate, 1),
        "margin_warning": margin_rate < 15,
        "valid_until": str(date.today() + timedelta(days=14)),
        "delivery_date": str(date.today() + timedelta(days=28)),
        "disclaimer": "演示系统生成，仅用于社会实践成果展示。",
    }

