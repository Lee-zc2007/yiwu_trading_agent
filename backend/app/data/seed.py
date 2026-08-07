import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from ..models import Customer, Merchant, RiskEvent, RiskRuleConfig, Transaction
from ..risk.scoring import CreditScoringService
from ..risk.service import RiskAssessmentService


RULE_CONFIGS = [
    ("AMOUNT_SURGE", "订单金额超过历史均值倍数", {"multiple": 5}, "high"),
    ("AMOUNT_ZSCORE", "订单金额超过均值加三倍标准差", {"zscore": 3}, "high"),
    ("SMALL_TO_LARGE", "连续小额试单后突然大额采购", {"small_limit": 8000, "large_multiple": 5}, "critical"),
    ("HIGH_FREQUENCY", "24 小时内异常高频下单", {"orders_24h": 4}, "high"),
    ("PAYMENT_CHANGED", "付款方式突然改变", {}, "medium"),
    ("COUNTRY_CHANGED", "收货国家突然改变", {}, "high"),
    ("ADDRESS_VOLATILITY", "短期频繁更换收货地址", {"window_days": 30, "unique_addresses": 3}, "high"),
    ("CATEGORY_CHANGED", "采购品类明显变化", {"dominant_share": 0.6}, "medium"),
    ("PROFILE_CHANGE_LARGE_ORDER", "资料变更后立即大额下单", {"hours": 72, "multiple": 3}, "critical"),
    ("SPLIT_ORDERS", "疑似拆单规避审核", {"audit_threshold": 50000, "near_ratio": 0.75, "min_orders": 3}, "critical"),
    ("CONSECUTIVE_ADVERSE", "连续逾期、退款或纠纷", {"consecutive": 3}, "high"),
    ("NEW_CUSTOMER_LARGE_ORDER", "新客户首单金额过高", {"amount": 20000}, "high"),
]

COMPANIES = [
    ("Claire Martin", "Maison Durable SAS", "France"), ("Ethan Walker", "Pacific Retail LLC", "United States"),
    ("Omar Hassan", "Gulf Horizon Trading", "UAE"), ("Anna Keller", "Nordlicht GmbH", "Germany"),
    ("Lucas Silva", "Mercado Verde Ltda", "Brazil"), ("Kenji Sato", "Mirai Commerce KK", "Japan"),
    ("Aisha Rahman", "Crescent Gifts FZE", "UAE"), ("Mateo Ruiz", "Iberia Home SL", "Spain"),
    ("Sophie Bernard", "Atelier Monde SARL", "France"), ("Noah Smith", "Northstar Imports Inc", "Canada"),
    ("Elena Rossi", "Vita Bella SRL", "Italy"), ("Min-jun Kim", "Han River Retail", "South Korea"),
    ("Nadia Petrova", "Baltic Select OU", "Estonia"), ("Ahmed Saleh", "Nile Trade Co", "Egypt"),
    ("Mia Johnson", "Urban Trail LLC", "United States"), ("Thomas Weber", "Rhein Markt GmbH", "Germany"),
    ("Yuki Tanaka", "Sakura Living KK", "Japan"), ("Fatima Noor", "Pearl Gate Trading", "Saudi Arabia"),
    ("Daniel Brown", "Atlas Wholesale Ltd", "United Kingdom"), ("Isabella Costa", "Sol Casa SA", "Portugal"),
]
CATEGORIES = ["家居用品", "户外用品", "礼品", "文具", "小家电", "宠物用品"]
PAYMENTS = ["T/T 30/70", "T/T 50/50", "Letter of Credit"]


def seed_demo_data(db: Session) -> None:
    if db.query(Merchant).count() > 0:
        return
    rng = random.Random(42)
    merchant = Merchant(name="义乌远航贸易示范商户", contact="demo@tradeguard.local")
    db.add(merchant); db.flush()
    for code, name, thresholds, severity in RULE_CONFIGS:
        db.add(RiskRuleConfig(rule_code=code, rule_name=name, threshold_config=thresholds, severity=severity, version="rules_v1"))

    today = datetime.now(UTC).replace(tzinfo=None, hour=10, minute=0, second=0, microsecond=0)
    customers: list[Customer] = []
    for index, (name, company, country) in enumerate(COMPANIES):
        customer = Customer(
            merchant_id=merchant.id, name=name, company_name=company, country=country,
            region="Europe" if country in {"France", "Germany", "Spain", "Italy", "Portugal", "Estonia", "United Kingdom"} else "Global",
            registration_number=f"DEMO-{country[:2].upper()}-{10000 + index}", email=f"contact{index + 1}@example.com",
            phone=f"+86 138 0000 {index:04d}", industry="Retail & Wholesale", main_product_category=CATEGORIES[index % len(CATEGORIES)],
            identity_verified=index not in {1, 13, 17}, cooperation_start_date=date.today() - timedelta(days=30 + index * 75),
            watchlist_status=index in {9, 10, 13}, blacklist_status=index == 13,
            notes="虚构演示外商数据，不对应任何真实企业或个人。",
        )
        if index == 8:
            customer.profile_updated_at = today - timedelta(hours=12)
        db.add(customer); db.flush(); customers.append(customer)

        base_amount = 3500 + index * 620
        dominant_category = CATEGORIES[index % len(CATEGORIES)]
        for order_index in range(15):
            order_time = today - timedelta(days=(14 - order_index) * 4 + index % 3)
            amount = max(500, rng.gauss(base_amount, base_amount * .12))
            payment = PAYMENTS[index % len(PAYMENTS)]
            shipping_country = country
            address = f"{100 + index} Demo Avenue, {country}"
            category = dominant_category
            overdue, refund, dispute, cancelled = 0, "none", "none", False

            # 通过确定性异常模式覆盖规则引擎和路演场景。
            if index == 4 and order_index == 14: amount *= 8
            if index == 5 and order_index >= 11: address = f"Temporary Address {order_index}, {country}"
            if index == 6 and order_index >= 12: amount = 42000 + (order_index - 12) * 900
            if index == 6 and order_index >= 12: order_time = today - timedelta(hours=(14 - order_index) * 8)
            if index == 7 and order_index == 14: category = "工业机械"
            if index == 8 and order_index == 14: amount *= 5
            if index == 9 and order_index >= 12: overdue, refund = 18, "requested"
            if index == 10 and order_index % 3 == 0: dispute = "open"
            if index == 11 and order_index == 14: payment = "Open Account 90 days"
            if index == 12 and order_index == 14: shipping_country, address = "Unknown", "Forwarding Warehouse #7"
            if index == 13 and order_index >= 11: order_time = today - timedelta(hours=16 - (order_index - 11) * 4)
            if index == 14 and order_index == 14: cancelled = True

            tx = Transaction(
                merchant_id=merchant.id, customer_id=customer.id, order_number=f"TG-{index + 1:02d}-{order_index + 1:03d}",
                product_category=category, product_name=f"{category}演示商品 {order_index + 1}", amount=round(amount, 2), currency="USD",
                order_time=order_time, payment_time=order_time + timedelta(days=min(7 + overdue, 60)),
                shipping_time=order_time + timedelta(days=3), delivery_time=order_time + timedelta(days=18), payment_method=payment,
                deposit_ratio=.3 if payment != "Open Account 90 days" else 0, final_payment_status="paid" if overdue < 15 else "overdue",
                refund_status=refund, dispute_status=dispute, overdue_days=overdue, cancelled=cancelled,
                shipping_country=shipping_country, shipping_address=address,
            )
            db.add(tx)
    db.commit()

    for customer in customers:
        CreditScoringService(db, merchant.id).calculate(customer)
    db.commit()

    # 对十个异常客户的最后一笔订单运行真实风控服务，生成可追溯预警。
    for customer in customers[4:14]:
        tx = db.query(Transaction).filter(Transaction.customer_id == customer.id).order_by(Transaction.order_time.desc()).first()
        order = {column.name: getattr(tx, column.name) for column in Transaction.__table__.columns}
        RiskAssessmentService(db, merchant.id).analyze_order(customer, order, tx.id, persist_event=True)
    db.commit()
    while db.query(RiskEvent).count() < 10:
        customer = customers[db.query(RiskEvent).count()]
        db.add(RiskEvent(merchant_id=merchant.id, customer_id=customer.id, risk_type="DEMO_REVIEW", risk_level="medium", risk_score=48, title=f"{customer.company_name} 资料复核", description="演示用风险事件", evidence={"data_type": "demo"}))
        db.commit()
