from datetime import date
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..data.seed import reset_demo_data
from ..models import AfterSalesCase, Customer, DemoScenario, Inquiry, Order, Product, Quote, ResearchMetric, RiskAssessment
from ..schemas.common import (
    ChatRequest,
    ContractAnalysisResponse,
    ContractAnalyzeRequest,
    DashboardResponse,
    HealthResponse,
    ImpactRequest,
    InquiryCreateRequest,
    LogisticsRequest,
    ProductCreateRequest,
    ProductGenerateRequest,
    ProductResponse,
    QuoteCalculationResponse,
    QuoteCalculateRequest,
    RiskEvaluationResponse,
    RiskEvaluateRequest,
    StatusUpdateRequest,
)
from ..services.ai_service import get_ai_provider
from ..services.contract_service import analyze_contract
from ..services.impact_service import calculate_impact
from ..services.pdf_service import build_quote_pdf
from ..services.quote_service import calculate_quote
from ..services.risk_service import evaluate_risk


router = APIRouter(prefix="/api")


def row(item: Any) -> dict:
    return {column.key: getattr(item, column.key) for column in sa_inspect(item).mapper.column_attrs}


def get_or_404(db: Session, model, item_id: int):
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="演示数据不存在")
    return item


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    return {"status": "ok", "service": "Yiwu AI Trade Copilot", "mode": settings.ai_provider, "products": db.query(Product).count(), "date": str(date.today())}


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard():
    return {
        "metrics": [
            {"label": "今日询盘", "value": 42, "change": "+18%", "tone": "blue"},
            {"label": "有效询盘", "value": 31, "change": "73.8%", "tone": "cyan"},
            {"label": "高意向客户", "value": 12, "change": "+3", "tone": "green"},
            {"label": "今日订单", "value": 8, "change": "+14%", "tone": "violet"},
            {"label": "预计成交金额", "value": 128600, "prefix": "¥", "change": "+22%", "tone": "gold"},
            {"label": "预计利润", "value": 38600, "prefix": "¥", "change": "30.0%", "tone": "green"},
            {"label": "风险订单", "value": 3, "change": "已拦截2笔", "tone": "red"},
            {"label": "AI自动处理率", "value": 72, "suffix": "%", "change": "+8pp", "tone": "cyan"},
            {"label": "平均回复", "value": 8, "suffix": "秒", "change": "原15分钟", "tone": "blue"},
            {"label": "平均风险分", "value": 34, "suffix": "/100", "change": "中低风险", "tone": "violet"},
        ],
        "inquiry_trend": [{"day": day, "inquiries": value, "valid": valid} for day, value, valid in [("7/27", 24, 17), ("7/28", 29, 22), ("7/29", 27, 19), ("7/30", 35, 25), ("7/31", 33, 26), ("8/1", 38, 29), ("8/2", 42, 31)]],
        "sources": [{"name": name, "value": value} for name, value in [("数字展台", 36), ("跨境平台", 27), ("社交媒体", 18), ("展会转介", 12), ("老客复购", 7)]],
        "countries": [{"name": name, "value": value} for name, value in [("法国", 28), ("美国", 24), ("西班牙", 17), ("阿联酋", 13), ("德国", 11)]],
        "funnel": [{"name": name, "value": value} for name, value in [("访问展台", 1280), ("AI对话", 426), ("有效询盘", 188), ("已报价", 96), ("成交订单", 41)]],
        "risks": [{"name": name, "value": value, "color": color} for name, value, color in [("低风险", 54, "#2fd1a4"), ("中风险", 28, "#f4bd50"), ("高风险", 13, "#ff865f"), ("极高风险", 5, "#f4576c")]],
        "time_saving": [{"task": task, "manual": manual, "ai": ai} for task, manual, ai in [("客户回复", 15, 0.13), ("生成报价", 20, 0.5), ("询盘总结", 12, 0.3), ("风险初筛", 18, 0.8)]],
        "products": [{"name": "EcoPulse保温杯", "heat": 96}, {"name": "SolarGo太阳能灯", "heat": 92}, {"name": "LumiNest氛围灯", "heat": 89}, {"name": "FlexPack旅行包", "heat": 84}],
        "order_status": [{"name": "待付款", "value": 8}, {"name": "生产中", "value": 16}, {"name": "运输中", "value": 11}, {"name": "已完成", "value": 28}],
        "disclaimer": "Dashboard 数据均为 Demo 模拟测算。",
    }


@router.get("/products", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    return [row(item) for item in db.query(Product).order_by(Product.popularity.desc()).all()]


@router.post("/products", response_model=ProductResponse)
def create_product(payload: ProductCreateRequest, db: Session = Depends(get_db)):
    if db.query(Product).filter(Product.sku == payload.sku).first():
        raise HTTPException(status_code=409, detail="SKU 已存在")
    item = Product(**payload.model_dump(), image="custom", multilingual_points="待AI生成", model_config='{"shape":"box","color":"#5b8cff"}', popularity=60)
    db.add(item)
    db.commit()
    db.refresh(item)
    return row(item)


@router.post("/products/generate")
def generate_product(payload: ProductGenerateRequest):
    return get_ai_provider().generate_product_concept(payload.model_dump())


@router.get("/products/{item_id}", response_model=ProductResponse)
def product_detail(item_id: int, db: Session = Depends(get_db)):
    return row(get_or_404(db, Product, item_id))


@router.post("/ai/chat")
def ai_chat(payload: ChatRequest):
    return get_ai_provider().chat_with_customer(payload.model_dump())


@router.get("/customers")
def list_customers(db: Session = Depends(get_db)):
    return [row(item) for item in db.query(Customer).order_by(Customer.id).all()]


@router.get("/customers/{item_id}")
def customer_detail(item_id: int, db: Session = Depends(get_db)):
    customer = get_or_404(db, Customer, item_id)
    inquiries = db.query(Inquiry).filter(Inquiry.customer_id == item_id).all()
    risk = db.query(RiskAssessment).filter(RiskAssessment.customer_id == item_id).order_by(RiskAssessment.id.desc()).first()
    return {**row(customer), "inquiries": [row(item) for item in inquiries], "assessment": row(risk) if risk else None}


@router.get("/inquiries")
def list_inquiries(db: Session = Depends(get_db)):
    items = []
    for inquiry in db.query(Inquiry).order_by(Inquiry.id.desc()).all():
        customer = db.get(Customer, inquiry.customer_id)
        product = db.get(Product, inquiry.product_id)
        items.append({**row(inquiry), "customer": customer.company if customer else "未知", "country": customer.country if customer else "", "product": product.name if product else "未知"})
    return items


@router.post("/inquiries")
def create_inquiry(payload: InquiryCreateRequest, db: Session = Depends(get_db)):
    customer = get_or_404(db, Customer, payload.customer_id)
    product = get_or_404(db, Product, payload.product_id)
    number = f"INQ-{date.today().strftime('%Y%m%d')}-{db.query(Inquiry).count() + 1:03d}"
    intent = 78 if payload.quantity >= product.moq else 54
    risk = 18 if customer.credit_score >= 80 else 42 if customer.credit_score >= 60 else 72
    item = Inquiry(**payload.model_dump(), inquiry_no=number, status="待处理", intent_score=intent, risk_score=risk, ai_summary=f"{customer.country}客户采购{product.name} {payload.quantity}件，目标价${payload.target_price:.2f}。", recommended_action="核实包装和交期后生成阶梯报价", urgent_language=False, account_changes=0)
    db.add(item)
    db.commit()
    db.refresh(item)
    return row(item)


@router.get("/inquiries/{item_id}")
def inquiry_detail(item_id: int, db: Session = Depends(get_db)):
    inquiry = get_or_404(db, Inquiry, item_id)
    return {**row(inquiry), "customer": row(get_or_404(db, Customer, inquiry.customer_id)), "product": row(get_or_404(db, Product, inquiry.product_id))}


@router.patch("/inquiries/{item_id}")
def update_inquiry(item_id: int, payload: StatusUpdateRequest, db: Session = Depends(get_db)):
    item = get_or_404(db, Inquiry, item_id)
    item.status = payload.status
    db.commit()
    db.refresh(item)
    return row(item)


@router.get("/quotes")
def list_quotes(db: Session = Depends(get_db)):
    return [row(item) for item in db.query(Quote).order_by(Quote.id.desc()).all()]


@router.post("/quotes/calculate", response_model=QuoteCalculationResponse)
def quote_preview(payload: QuoteCalculateRequest):
    return calculate_quote(payload.model_dump())


@router.post("/quotes")
def create_quote(payload: QuoteCalculateRequest, db: Session = Depends(get_db)):
    calculation = calculate_quote(payload.model_dump())
    quote_no = f"QT-{date.today().strftime('%Y%m%d')}-{db.query(Quote).count() + 1:03d}"
    item = Quote(
        quote_no=quote_no,
        inquiry_id=payload.inquiry_id,
        product_id=payload.product_id,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        discount=payload.discount,
        packaging_fee=payload.packaging_fee,
        freight=payload.freight,
        insurance=payload.insurance,
        tax=calculation["tax"],
        total_cost=calculation["total_cost"],
        total_amount=calculation["total_amount"],
        expected_profit=calculation["expected_profit"],
        margin_rate=calculation["margin_rate"],
        incoterm=payload.incoterm,
        valid_until=calculation["valid_until"],
        delivery_date=calculation["delivery_date"],
        status="已生成",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return row(item)


@router.post("/quotes/preview/pdf")
def quote_preview_pdf(payload: QuoteCalculateRequest, db: Session = Depends(get_db)):
    product = get_or_404(db, Product, payload.product_id)
    calculation = calculate_quote(payload.model_dump())
    content = build_quote_pdf(calculation, product.name)
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="yiwu-demo-quotation.pdf"'})


@router.get("/quotes/{item_id}/pdf")
def quote_pdf(item_id: int, db: Session = Depends(get_db)):
    item = get_or_404(db, Quote, item_id)
    quote = row(item)
    product = get_or_404(db, Product, item.product_id)
    content = build_quote_pdf(quote, product.name)
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{item.quote_no}.pdf"'})


@router.post("/risk/evaluate", response_model=RiskEvaluationResponse)
def risk_evaluate(payload: RiskEvaluateRequest):
    return evaluate_risk(payload.model_dump())


@router.get("/risk/customers/{customer_id}")
def customer_risk(customer_id: int, db: Session = Depends(get_db)):
    customer = get_or_404(db, Customer, customer_id)
    assessment = db.query(RiskAssessment).filter(RiskAssessment.customer_id == customer_id).order_by(RiskAssessment.id.desc()).first()
    if not assessment:
        raise HTTPException(status_code=404, detail="暂无风险评估")
    return {**row(assessment), "factors": json.loads(assessment.factors), "customer": row(customer), "disclaimer": "该风险评分为教学和演示模型，不构成真实征信或商业决策依据。"}


@router.post("/contracts/analyze", response_model=ContractAnalysisResponse)
def contract_analyze(payload: ContractAnalyzeRequest):
    return analyze_contract(payload.text)


@router.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    items = []
    for order in db.query(Order).order_by(Order.id.desc()).all():
        customer = db.get(Customer, order.customer_id)
        product = db.get(Product, order.product_id)
        items.append({**row(order), "customer": customer.company if customer else "未知", "product": product.name if product else "未知"})
    return items


@router.get("/orders/{item_id}")
def order_detail(item_id: int, db: Session = Depends(get_db)):
    order = get_or_404(db, Order, item_id)
    stages = ["询盘", "报价", "合同", "付款", "生产", "质检", "发货", "到港", "完成"]
    current = min(len(stages) - 1, round(order.progress / 100 * (len(stages) - 1)))
    timeline = [{"name": name, "status": "done" if index < current else "current" if index == current else "pending"} for index, name in enumerate(stages)]
    return {**row(order), "timeline": timeline, "customer": row(get_or_404(db, Customer, order.customer_id)), "product": row(get_or_404(db, Product, order.product_id))}


@router.post("/logistics/recommend")
def logistics_recommend(payload: LogisticsRequest):
    weight = payload.weight_kg
    volume = payload.volume_cbm
    return {
        "origin": payload.origin,
        "destination": payload.destination,
        "plans": [
            {"mode": "海运", "cost": round(650 + volume * 115 + weight * 0.12), "days": 30, "risk": "低", "carbon_kg": round(weight * 0.12), "recommendation": 91, "tag": "综合推荐"},
            {"mode": "中欧班列", "cost": round(980 + volume * 150 + weight * 0.24), "days": 18, "risk": "中低", "carbon_kg": round(weight * 0.28), "recommendation": 86, "tag": "时效平衡"},
            {"mode": "空运", "cost": round(480 + weight * 4.6), "days": 6, "risk": "低", "carbon_kg": round(weight * 1.75), "recommendation": 72 if payload.desired_days < 10 else 58, "tag": "极速"},
        ],
        "disclaimer": "费用、时效与碳排放均为演示模拟值。",
    }


@router.get("/after-sales")
def after_sales(db: Session = Depends(get_db)):
    cases = [row(item) for item in db.query(AfterSalesCase).order_by(AfterSalesCase.id.desc()).all()]
    return {"cases": cases, "summary": {"average_satisfaction": 4.3, "average_handle_hours": 9.6, "repurchase_rate": 76, "open_cases": 3}, "satisfaction_trend": [{"month": month, "score": score} for month, score in [("3月", 4.0), ("4月", 4.1), ("5月", 4.2), ("6月", 4.25), ("7月", 4.4), ("8月", 4.5)]], "categories": [{"name": "包装", "value": 32}, {"name": "物流", "value": 28}, {"name": "质量", "value": 22}, {"name": "色差", "value": 18}], "keywords": ["响应快", "包装", "交期", "可靠", "色差", "定制"]}


@router.post("/analytics/impact")
def analytics_impact(payload: ImpactRequest):
    return calculate_impact(payload.model_dump())


@router.get("/research/metrics")
def research_metrics(db: Session = Depends(get_db)):
    return {"metrics": [row(item) for item in db.query(ResearchMetric).order_by(ResearchMetric.id).all()], "findings": ["数字工具显著提高获客、翻译与沟通效率", "客户身份核验和线上交易信任仍是突出短板", "商户需要把碎片化工具连接为完整贸易闭环"], "quotes": ["以前做生意靠见面、靠熟人，现在一个视频就能让客户看到工厂。", "AI能帮我说外语，但这个客户到底靠不靠谱，还是最担心的。", "快不只是回复快，更重要的是少踩坑、敢接单。"], "methodology": ["商户半结构化访谈", "市场现场观察", "问卷与案例归纳", "原型验证与情景推演"], "notice": "占位字段需在真实调研完成后替换。"}


@router.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    reset_demo_data(db)
    return {"message": "演示数据已重置", "status": "ok"}


@router.get("/demo/scenarios")
def demo_scenarios(db: Session = Depends(get_db)):
    result = []
    for item in db.query(DemoScenario).order_by(DemoScenario.code).all():
        result.append({**row(item), "messages": json.loads(item.messages)})
    return result
