from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def build_quote_pdf(quote: dict, product_name: str) -> bytes:
    buffer = BytesIO()
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("cn-title", parent=styles["Title"], fontName="STSong-Light", textColor=colors.HexColor("#0B2340"), fontSize=20)
    normal = ParagraphStyle("cn-normal", parent=styles["BodyText"], fontName="STSong-Light", fontSize=10, leading=16)
    story = [Paragraph("Yiwu AI Trade Copilot", title), Paragraph("中英文智能报价单 / Bilingual Quotation", normal), Spacer(1, 8 * mm)]
    data = [
        ["报价编号 Quote No.", quote.get("quote_no", "PREVIEW")],
        ["产品 Product", product_name],
        ["数量 Quantity", f"{quote['quantity']:,}"],
        ["单价 Unit Price", f"USD {quote['unit_price']:,.2f}"],
        ["贸易术语 Incoterm", quote["incoterm"]],
        ["包装费 Packaging", f"USD {quote['packaging_fee']:,.2f}"],
        ["运费 Freight", f"USD {quote['freight']:,.2f}"],
        ["保险 Insurance", f"USD {quote['insurance']:,.2f}"],
        ["报价总额 Total", f"USD {quote['total_amount']:,.2f}"],
        ["有效期 Valid Until", quote["valid_until"]],
        ["预计交货 Delivery", quote["delivery_date"]],
    ]
    table = Table(data, colWidths=[62 * mm, 92 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"), ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F1FA")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#173E68")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B9CADB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([table, Spacer(1, 8 * mm), Paragraph("说明：本报价由演示系统生成，仅用于社会实践成果展示，不构成正式商业要约。", normal), Paragraph("Demo notice: Generated for educational presentation only and not a binding commercial offer.", normal)])
    doc.build(story)
    return buffer.getvalue()

