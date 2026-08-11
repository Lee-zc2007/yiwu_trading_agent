"""可离线路演的外贸风控知识样例。

这些内容是通用操作经验，不包含任何客户、订单、评分或风险事件数据。
"""

from sqlalchemy.orm import Session

from ..models import KnowledgeBase
from ..services.knowledge_base import KnowledgeBaseService


DEMO_KNOWLEDGE_DOCUMENTS = [
    {
        "title": "小额试单后突然大额采购案例",
        "category": "risk_case",
        "content": (
            "某外贸商户与新客户连续完成多笔小额试单，付款和收货均正常，随后客户突然提出远高于历史均值的大额订单，"
            "并要求降低定金、加快发货。商户没有核实付款账户主体和最终收货人便安排生产，后续出现尾款拖欠。"
            "复盘要点：历史履约正常不能替代本次订单核验；金额突增、付款条件放宽和交期压缩同时出现时，应提高人工复核等级，"
            "核对合同主体、付款账户、收货主体，并采用足额定金或分批交付。该案例只提供风险迹象和核验经验，不代表相似客户必然违约。"
        ),
    },
    {
        "title": "义乌市场付款账户变更核验经验",
        "category": "yiwu_market_experience",
        "content": (
            "义乌市场外贸交易中，客户可能因代理采购、跨境结算或集团财务安排提出第三方付款。遇到付款账户突然变更时，"
            "应通过原登记联系方式进行二次确认，要求客户提供盖章说明，核对付款人、合同买方和发票抬头之间的关系。"
            "如同时发生收货地址变更、货代变更或催促立即发货，应暂停自动放行并转人工复核。不要仅凭聊天软件中的新账号通知修改收款或发货信息。"
        ),
    },
    {
        "title": "义乌市场大额订单分批交付经验",
        "category": "yiwu_market_experience",
        "content": (
            "当订单金额明显高于既往合作规模时，可将生产、验货、付款和发货拆分为可核验节点。常见做法包括提高定金比例、"
            "约定中期验货、按批次确认尾款到账后放货，并保留合同、付款水单、物流委托和验货记录。分批交付是风险缓释措施，"
            "不能替代客户身份、资金来源及贸易背景核验。"
        ),
    },
    {
        "title": "外贸合同付款与货权风险条款",
        "category": "contract_risk_rule",
        "content": (
            "合同应明确买卖双方主体、币种、付款节点、定金比例、尾款到账条件、货权转移时点和逾期责任。"
            "对赊销、远期付款或第三方付款，应写明授权关系、信用额度和触发暂停履约的条件。变更收货地址、付款账户、货代或贸易术语时，"
            "应采用书面变更文件并由授权人员确认。合同条款审查属于风险控制参考，复杂交易仍需专业法律人员复核。"
        ),
    },
    {
        "title": "高风险订单人工复核操作规范",
        "category": "risk_operation_standard",
        "content": (
            "高风险订单进入人工复核后，应依次完成：核验客户注册与受益人信息；通过原始联系方式回访；核对合同、订单、付款账户和收货主体；"
            "检查近期地址、付款方式和采购品类变化；复核历史逾期、退款与纠纷；记录证据和复核结论。"
            "系统风险分和异常模型只用于排序与提示，复核人员不得把异常直接定性为欺诈，也不得由 Agent 自动加入黑名单或暂停发货。"
        ),
    },
    {
        "title": "单据与物流信息一致性操作规范",
        "category": "risk_operation_standard",
        "content": (
            "发货前应核对商业发票、装箱单、合同、报关信息、收货地址和货代委托的一致性。若最终收货国家与客户注册地或历史线路不同，"
            "需要记录商业原因并验证最终收货主体。对临时仓库、转运地址和频繁更换货代的情形，应补充物流链路证明并由人工确认是否放行。"
        ),
    },
]


def seed_knowledge_base(db: Session) -> None:
    """知识库为空时写入通用演示知识，不接触结构化交易数据。"""

    if db.query(KnowledgeBase.id).first():
        return
    service = KnowledgeBaseService(db)
    for document in DEMO_KNOWLEDGE_DOCUMENTS:
        service.ingest_document(document["title"], document["content"], document["category"])
    db.commit()


__all__ = ["DEMO_KNOWLEDGE_DOCUMENTS", "seed_knowledge_base"]
