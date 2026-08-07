# 风控引擎说明

## 信用评分

总分为五个 0–100 子分的加权和：履约表现 30%、交易稳定性 20%、纠纷退款 20%、身份完整性 15%、合作关系 15%。黑名单客户总分上限为 25。交易数 0–2、3–9、10+ 分别对应低、中、高置信度。每次重算都会写入 `credit_score_history`，规则版本为 `credit_v1`。

分级：90+ 低风险优质客户、75–89.99 较低风险、60–74.99 中等风险、40–59.99 较高风险、低于 40 高风险。

## 规则

规则由 `risk_rule_configs` 提供启用状态、阈值、严重度和版本，代码实现位于 `backend/app/risk/rules/builtin.py`。

| 规则代码 | 主要迹象 |
|---|---|
| AMOUNT_SURGE | 金额达到历史均值指定倍数 |
| AMOUNT_ZSCORE | 金额超过均值若干标准差 |
| SMALL_TO_LARGE | 连续小额试单后突然放大 |
| HIGH_FREQUENCY | 24 小时内高频下单 |
| PAYMENT_CHANGED | 常用付款方式改变 |
| COUNTRY_CHANGED | 常用收货国家改变 |
| ADDRESS_VOLATILITY | 30 天内地址数量异常 |
| CATEGORY_CHANGED | 稳定采购品类突然改变 |
| PROFILE_CHANGE_LARGE_ORDER | 资料变更后短时大额下单 |
| SPLIT_ORDERS | 多笔接近审核阈值且总额异常 |
| CONSECUTIVE_ADVERSE | 连续逾期、退款或纠纷 |
| NEW_CUSTOMER_LARGE_ORDER | 无历史客户首单过大 |

## 异常模型

训练和推理均调用 `extract_order_features`，共 14 个特征：金额、均值倍率、Z-score、近 7 日单数、近 30 日金额、付款延迟、定金比例、历史退款/纠纷/取消率、近 30 日地址数、付款方式变化、品类变化和历史交易数。

Isolation Forest 使用固定随机种子 42、RobustScaler 和 180 棵树。原始 decision score 按训练集 5%/95% 分位映射为 0–1 异常度。artifact 缺失时自动训练；样本不足或载入失败时使用金额偏离、付款/品类变化和不良履约组成的统计分。

## 综合分

综合风险由信用风险 25%、最高规则风险 35%、统计异常 15%、Isolation Forest 异常度 25% 组合，并依据多规则命中和黑名单状态做有限上调。服务返回 low/medium/high/critical，而不是“欺诈/非欺诈”。

保存的风险事件包含订单 ID、客户 ID、总体分、全部规则证据、特征快照、模型/规则版本、生成时间和建议，便于回放。
