from abc import ABC, abstractmethod
import json

import httpx

from ..core.config import settings
from .contract_service import analyze_contract


class AIProvider(ABC):
    @abstractmethod
    def generate_product_concept(self, data: dict) -> dict: ...

    @abstractmethod
    def chat_with_customer(self, data: dict) -> dict: ...

    def summarize_inquiry(self, text: str) -> dict:
        return {"summary": f"采购商关注价格、MOQ与交期。原始需求摘要：{text[:120]}", "intent_score": 76, "next_action": "发送阶梯报价并确认包装规格"}

    def translate_text(self, text: str, language: str) -> dict:
        return {"translated": text, "language": language, "provider": "mock"}

    def generate_quote_content(self, quote: dict) -> dict:
        return {"subject": "Yiwu Trade Quotation", "notes": "Price includes the selected trade terms. Valid for 14 days.", "quote": quote}

    def analyze_contract(self, text: str) -> dict:
        return analyze_contract(text)

    def recommend_followup(self, context: str) -> dict:
        return {"action": "24小时内发送样品图与阶梯报价", "message": f"基于当前上下文建议聚焦确认预算和交期：{context[:100]}"}


class MockAIProvider(AIProvider):
    def generate_product_concept(self, data: dict) -> dict:
        category = data["category"]
        country = data["target_country"]
        color = data["color"]
        seed = sum(ord(ch) for ch in category + country) % 7
        match = 86 + seed
        return {
            "name": f"{color} · EcoPulse {category}",
            "positioning": f"面向{country}{data['target_customer']}的高性价比可持续生活产品",
            "concept": f"以{data['style']}为核心，将义乌柔性供应链与{data['usage']}场景结合。",
            "palette": [color, "云雾白", "深海蓝"],
            "packaging": "FSC纸浆一体包装，可选中英双语与目的国标签",
            "selling_points": ["环保材料可追溯", "小批量快速定制", "支持多语言包装", "耐用结构与模块化配件"],
            "suggested_price": data["price_range"],
            "target_market": country,
            "market_match_score": match,
            "estimated_margin_rate": 31 + seed,
            "estimated_lead_days": 18 + seed,
            "image_variant": seed % 3,
            "provider": "MockAIProvider",
            "process": ["解析目标市场", "匹配调研洞察", "生成设计语言", "评估供应链可行性"],
        }

    def chat_with_customer(self, data: dict) -> dict:
        message = data["message"].lower()
        scenario = data.get("scenario")
        intent = 68
        risk = 18
        stage = "需求澄清"
        concerns = ["价格", "MOQ"]
        if any(key in message for key in ["discount", "lower price", "降价", "便宜"]):
            reply = "可以按数量提供阶梯价格：1,000件为 $12.80，3,000件可至 $11.90。若采用标准包装，还可再优化约2%。您希望先看正式报价吗？"
            intent, stage, concerns = 86, "议价", ["阶梯价格", "包装成本", "交期"]
        elif any(key in message for key in ["eco", "环保", "recycl", "bpa"]):
            reply = "推荐 EcoPulse 环保保温杯：食品级304不锈钢、BPA-free杯盖与FSC包装，MOQ 500件，常规交期18天，也支持法语包装。"
            intent, stage, concerns = 82, "产品匹配", ["环保认证", "材料", "定制包装"]
        elif any(key in message for key in ["cod", "货到付款", "refuse", "不提供", "crypto", "bitcoin"]):
            reply = "为保障双方交易安全，大额首单需完成公司信息核验，并采用30%预付款与发货前尾款。我们暂不接受无身份资料的货到付款。"
            intent, risk, stage, concerns = 61, 88, "风险核验", ["付款方式", "身份验证", "账户安全"]
        elif any(key in message for key in ["lead", "delivery", "交期", "多久"]):
            reply = "现货样品48小时内可发出；500至2,000件的定制订单预计18—24天完成生产，海运到欧洲通常另需25—32天。"
            intent, stage, concerns = 74, "交付确认", ["生产周期", "物流时效"]
        elif any(key in message for key in ["quote", "quotation", "报价"]):
            reply = "当然可以。请确认数量、目的港和贸易术语（EXW/FOB/CIF），我会在30秒内生成中英文报价单。"
            intent, stage, concerns = 88, "报价准备", ["数量", "目的港", "贸易术语"]
        else:
            reply = "欢迎来到义乌数字展台。我可以为您推荐商品、说明MOQ与交期，或根据数量即时生成报价。请告诉我目标市场和采购数量。"
        if scenario == "C":
            risk = max(risk, 82)
        amount = round((3000 if intent > 80 else 1200) * 12.8, 0)
        return {
            "reply": reply,
            "intent_score": intent,
            "estimated_order_amount": amount,
            "concerns": concerns,
            "stage": stage,
            "risk_score": risk,
            "risk_tip": "建议暂停自动报价并核验企业身份" if risk >= 60 else "当前未发现显著异常，继续收集需求",
            "recommended_reply": "请确认采购数量、目的港和期望交期，我将生成最合适的方案。",
            "next_action": "身份核验" if risk >= 60 else "生成阶梯报价" if intent >= 80 else "继续澄清需求",
            "provider": "MockAIProvider",
        }


class OpenAICompatibleProvider(MockAIProvider):
    def _request(self, system: str, user: str) -> dict | None:
        if not settings.openai_api_key:
            return None
        try:
            response = httpx.post(
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={"model": settings.openai_model, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                timeout=25,
            )
            response.raise_for_status()
            return json.loads(response.json()["choices"][0]["message"]["content"])
        except Exception:
            return None

    def generate_product_concept(self, data: dict) -> dict:
        result = self._request("你是义乌产品设计助手。只返回JSON。", json.dumps(data, ensure_ascii=False))
        if result:
            return {**result, "provider": "OpenAICompatibleProvider"}
        return {**super().generate_product_concept(data), "fallback": True}

    def chat_with_customer(self, data: dict) -> dict:
        result = self._request("你是多语言外贸销售助手。只返回JSON，含reply,intent_score,stage,risk_score,next_action。", json.dumps(data, ensure_ascii=False))
        if result:
            return {**result, "provider": "OpenAICompatibleProvider"}
        return {**super().chat_with_customer(data), "fallback": True}


def get_ai_provider() -> AIProvider:
    if settings.ai_provider in {"openai", "real"}:
        return OpenAICompatibleProvider()
    return MockAIProvider()

