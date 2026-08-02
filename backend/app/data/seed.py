import json
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import AfterSalesCase, Customer, DemoScenario, Inquiry, Order, Product, Quote, ResearchMetric, RiskAssessment


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


PRODUCTS = [
    dict(name="EcoPulse环保保温杯", category="家居日用", sku="YAT-CUP-001", image="cup", description="304食品级不锈钢、BPA-free杯盖，支持多语言包装与小批量定制。", price=12.8, cost=7.6, moq=500, stock=8600, lead_days=18, target_markets="法国,德国,西班牙", tags="环保,热销,可定制", multilingual_points="EN: Sustainable & BPA-free | FR: Durable et écologique", model_config='{"shape":"cylinder","color":"#31c6a4"}', popularity=96),
    dict(name="LumiNest氛围灯", category="家居装饰", sku="YAT-LMP-012", image="lamp", description="USB-C充电、三档色温，可定制礼盒与Logo。", price=8.9, cost=4.7, moq=300, stock=5300, lead_days=15, target_markets="美国,英国,阿联酋", tags="家居,礼品,新品", multilingual_points="EN: Portable ambient light | AR: إضاءة محمولة", model_config='{"shape":"sphere","color":"#ffb45c"}', popularity=89),
    dict(name="FlexPack折叠旅行包", category="箱包", sku="YAT-BAG-023", image="bag", description="防泼水再生面料，折叠体积仅为普通旅行包的1/5。", price=6.6, cost=3.3, moq=800, stock=12000, lead_days=22, target_markets="美国,俄罗斯,巴西", tags="旅行,轻量,再生材料", multilingual_points="EN: Foldable & water resistant | ES: Ligera y plegable", model_config='{"shape":"box","color":"#5b8cff"}', popularity=84),
    dict(name="MiniChef硅胶厨具套装", category="厨具", sku="YAT-KIT-034", image="kitchen", description="食品级硅胶六件套，耐温230℃，适合电商礼盒。", price=9.5, cost=5.2, moq=600, stock=7400, lead_days=20, target_markets="法国,加拿大,澳大利亚", tags="厨房,套装,礼盒", multilingual_points="EN: Food-grade silicone set | FR: Kit silicone alimentaire", model_config='{"shape":"cone","color":"#e97988"}', popularity=78),
    dict(name="SolarGo便携太阳能灯", category="户外用品", sku="YAT-SOL-045", image="solar", description="IP65防水、太阳能与Type-C双充电，适合户外及应急使用。", price=14.2, cost=8.4, moq=400, stock=3900, lead_days=25, target_markets="南非,沙特,墨西哥", tags="太阳能,户外,应急", multilingual_points="EN: Solar emergency light | ES: Luz solar portátil", model_config='{"shape":"cylinder","color":"#ffd166"}', popularity=92),
]

CUSTOMERS = [
    dict(company="Maison Verte SAS", contact="Claire Martin", country="法国", email="claire@maisonverte.fr", phone="+33 *** 218", registered_years=11, historical_orders=18, historical_amount=286000, source="展会老客", intent_level="高", risk_level="低风险", credit_score=93, last_contact="今天 09:24", tags="长期客户,环保品类", profile_completeness=98, disputes=0, verification_refused=False),
    dict(company="Pacific Retail LLC", contact="Ethan Walker", country="美国", email="ethan@pacificretail.com", phone="+1 *** 804", registered_years=3, historical_orders=2, historical_amount=32800, source="数字展台", intent_level="高", risk_level="中风险", credit_score=72, last_contact="今天 10:18", tags="批量采购,议价敏感", profile_completeness=82, disputes=0, verification_refused=False),
    dict(company="Nova Import Group", contact="Alex Novak", country="波兰", email="novaimport@outlook.com", phone="+48 *** 119", registered_years=1, historical_orders=0, historical_amount=0, source="社交媒体", intent_level="中", risk_level="高风险", credit_score=42, last_contact="昨天 18:42", tags="新客户,付款异常", profile_completeness=54, disputes=1, verification_refused=False),
    dict(company="Global Fast Trade", contact="Samir K.", country="阿联酋", email="fasttrade2026@gmail.com", phone="未提供", registered_years=0, historical_orders=0, historical_amount=0, source="陌生邮件", intent_level="高", risk_level="极高风险", credit_score=16, last_contact="今天 11:05", tags="身份存疑,货到付款,异常催促", profile_completeness=25, disputes=2, verification_refused=True),
    dict(company="Mercado Soluciones", contact="Lucía Torres", country="西班牙", email="lucia@mercadosol.es", phone="+34 *** 503", registered_years=6, historical_orders=7, historical_amount=91400, source="跨境平台", intent_level="中", risk_level="低风险", credit_score=87, last_contact="3天前", tags="复购,家居用品", profile_completeness=91, disputes=0, verification_refused=False),
]

INQUIRIES = [
    dict(inquiry_no="INQ-20260802-001", customer_id=1, product_id=1, quantity=2200, target_price=11.9, payment_method="T/T 30/70", destination="Le Havre, France", expected_delivery="2026-09-25", status="已报价", intent_score=91, risk_score=12, ai_summary="法国长期客户寻找环保保温杯，重视FSC包装与法语标签。", recommended_action="发送样品确认并锁定生产排期", urgent_language=False, account_changes=0),
    dict(inquiry_no="INQ-20260802-002", customer_id=2, product_id=3, quantity=5000, target_price=5.8, payment_method="L/C", destination="Los Angeles, USA", expected_delivery="2026-10-10", status="跟进中", intent_score=86, risk_score=38, ai_summary="美国采购商计划大批量采购旅行包，目标价较低，可通过标准包装优化。", recommended_action="提供3,000/5,000/10,000件阶梯报价", urgent_language=False, account_changes=0),
    dict(inquiry_no="INQ-20260801-009", customer_id=3, product_id=2, quantity=15000, target_price=7.2, payment_method="个人账户转账", destination="Warsaw, Poland", expected_delivery="尽快", status="风险复核", intent_score=67, risk_score=71, ai_summary="首单金额显著偏高，要求个人账户结算且资料不完整。", recommended_action="暂停报价，完成企业与收货地址核验", urgent_language=True, account_changes=1),
    dict(inquiry_no="INQ-20260802-004", customer_id=4, product_id=5, quantity=30000, target_price=10.0, payment_method="货到付款 COD", destination="地址待定", expected_delivery="立即发货", status="已拦截", intent_score=74, risk_score=92, ai_summary="客户拒绝公司验证，要求超大首单货到付款并多次催促。", recommended_action="停止自动推进并提交人工反欺诈复核", urgent_language=True, account_changes=3),
    dict(inquiry_no="INQ-20260731-018", customer_id=5, product_id=4, quantity=1200, target_price=8.8, payment_method="T/T 40/60", destination="Valencia, Spain", expected_delivery="2026-09-18", status="待确认", intent_score=73, risk_score=19, ai_summary="复购客户新增厨具品类，关注欧盟食品接触材料说明。", recommended_action="发送合规资料与西语包装样稿", urgent_language=False, account_changes=0),
]

ORDERS = [
    dict(order_no="ORD-2026-0801", customer_id=1, product_id=1, quantity=2200, amount=27500, profit=8120, payment_status="已收预付款", production_status="生产中", logistics_status="待订舱", risk_status="低风险", expected_delivery="2026-09-25", progress=48),
    dict(order_no="ORD-2026-0733", customer_id=5, product_id=4, quantity=900, amount=8550, profit=2640, payment_status="已付清", production_status="质检中", logistics_status="待发货", risk_status="低风险", expected_delivery="2026-08-22", progress=72),
    dict(order_no="ORD-2026-0718", customer_id=2, product_id=3, quantity=3000, amount=19600, profit=4980, payment_status="待尾款", production_status="已完成", logistics_status="运输中", risk_status="中风险", expected_delivery="2026-08-30", progress=84),
    dict(order_no="ORD-2026-0692", customer_id=1, product_id=2, quantity=1000, amount=8900, profit=2450, payment_status="已付清", production_status="已完成", logistics_status="已到港", risk_status="低风险", expected_delivery="2026-08-05", progress=96),
]

AFTER_SALES = [
    dict(case_no="AS-2026-031", customer="Maison Verte SAS", category="包装破损", satisfaction=4.7, sentiment="正向", status="已解决", repurchase_probability=91, suggested_contact="2026-08-12", suggestion="发送环保包装升级方案与复购优惠"),
    dict(case_no="AS-2026-028", customer="Mercado Soluciones", category="颜色偏差", satisfaction=4.2, sentiment="中性", status="处理中", repurchase_probability=76, suggested_contact="2026-08-06", suggestion="确认色卡并补发小批量替换件"),
    dict(case_no="AS-2026-019", customer="Pacific Retail LLC", category="物流延误", satisfaction=3.8, sentiment="负向", status="已补偿", repurchase_probability=63, suggested_contact="2026-08-15", suggestion="提供优先排产与双物流备选方案"),
]

SCENARIOS = [
    dict(code="A", title="法国采购商寻找环保保温杯", description="展示多语言推荐、环保卖点与高意向识别。", language="fr", messages=json.dumps([{"role":"assistant","content":"Bonjour! Je suis votre assistant commercial IA à Yiwu."},{"role":"user","content":"We need eco-friendly insulated bottles with French packaging for 2,000 units."}], ensure_ascii=False), risk_hint="低风险"),
    dict(code="B", title="美国采购商大批量议价", description="展示阶梯报价、利润护栏与议价建议。", language="en", messages=json.dumps([{"role":"assistant","content":"Welcome! I can help with wholesale pricing and delivery options."},{"role":"user","content":"We need 5,000 travel bags, but your price must be lower."}], ensure_ascii=False), risk_hint="中风险"),
    dict(code="C", title="高风险货到付款客户", description="展示拒绝核验、异常付款与风险拦截。", language="en", messages=json.dumps([{"role":"assistant","content":"Before a large first order, we complete a quick company verification."},{"role":"user","content":"Ship 30,000 units COD today. I refuse to provide company information."}], ensure_ascii=False), risk_hint="极高风险"),
]


def reset_demo_data(db: Session):
    for model in [RiskAssessment, Quote, Order, Inquiry, AfterSalesCase, DemoScenario, ResearchMetric, Customer, Product]:
        db.execute(delete(model))
    db.add_all([Product(**item) for item in PRODUCTS])
    db.add_all([Customer(**item) for item in CUSTOMERS])
    db.add_all([Inquiry(**item) for item in INQUIRIES])
    db.add_all([Order(**item) for item in ORDERS])
    db.add_all([AfterSalesCase(**item) for item in AFTER_SALES])
    db.add_all([DemoScenario(**item) for item in SCENARIOS])
    metrics_path = DATA_DIR / "research_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else []
    db.add_all([ResearchMetric(**item) for item in metrics])
    risk_rows = [
        dict(customer_id=1, score=12, level="低风险", factors='[{"name":"注册年限","contribution":0},{"name":"历史成交","contribution":0},{"name":"付款方式","contribution":0},{"name":"资料完整度","contribution":1}]', explanation="长期稳定成交、企业资料完整、付款路径一致。", recommendation="可按常规30%预付款流程推进。"),
        dict(customer_id=2, score=38, level="中风险", factors='[{"name":"注册年限","contribution":7},{"name":"历史成交","contribution":5},{"name":"金额异常","contribution":6},{"name":"资料完整度","contribution":2}]', explanation="合作历史较短且本次订单增长较快。", recommendation="补充采购授权并采用30%预付款。"),
        dict(customer_id=3, score=71, level="高风险", factors='[{"name":"付款方式","contribution":18},{"name":"历史成交","contribution":10},{"name":"邮箱域名","contribution":7},{"name":"异常紧迫性","contribution":7}]', explanation="个人账户付款、首单金额异常且沟通存在催促。", recommendation="完成公司与地址核验，预付款提高至80%。"),
        dict(customer_id=4, score=92, level="极高风险", factors='[{"name":"身份验证","contribution":14},{"name":"付款方式","contribution":18},{"name":"账户变更","contribution":12},{"name":"行为一致性","contribution":10}]', explanation="拒绝验证、货到付款、地址缺失并频繁催促。", recommendation="暂停交易并提交独立人工复核。"),
    ]
    db.add_all([RiskAssessment(**item) for item in risk_rows])
    db.commit()


def seed_if_empty(db: Session):
    if db.query(Product).count() == 0:
        reset_demo_data(db)

