# 风控与交易决策引擎

## 六层确定性输出

`TransactionDecisionService` 统一编排以下能力，并以 `transaction_decision_v1` 标记计算版本：

1. Customer Trust：客户历史事实与数据置信度；
2. Transaction Risk：当前交易条件的规则风险；
3. Risk Exposure：未被已确认收款和已验证保障覆盖的货值；
4. Evidence Completeness：必需证据的加权完整度和关键缺失；
5. Risk Mitigation：真实可抵扣保障；
6. Credit Terms：建议交易条件与人工复核要求。

旧 `credit_v1` 信用分和 `/api/risk/analyze-order` 保留以兼容 MVP，但不再是新版页面和 Agent 的唯一决策中心。

## Customer Trust v2

Customer Trust 不把“未知”伪装成“正常”。只有存在明确付款到期日或可验证到期事件时，才计算按期付款表现；缺少到期依据时 `on_time_payment_rate=null`，并在 `missing_fields` 中声明数据缺口。

输出包括合作天数、交易次数、累计金额、历史最大订单、按期率、逾期次数/平均天数、退款率、纠纷率、拒付次数、身份状态、信任等级、置信度和版本。

## Transaction Risk rules_v2

每条规则返回 `rule_code`、`severity`、`risk_score`、`risk_contribution`、`reason` 和结构化 `evidence`。新版新增交易授信规则：

| 规则 | 含义 |
|---|---|
| `FIRST_CREDIT_EXPOSURE` | 首次合作即产生未收款敞口 |
| `LOW_DEPOSIT_RATIO` | 定金低于配置阈值 |
| `LONG_CREDIT_TERM` | 账期达到长账期阈值 |
| `CREDIT_TERM_EXTENSION` | 账期较历史最长水平明显延长 |
| `DEFERRED_FINAL_PAYMENT` | 尾款位于发货或交付后 |
| `PAYER_CONTRACT_MISMATCH` | 付款主体与合同主体不一致 |
| `PAYMENT_ACCOUNT_CHANGE` | 付款账户变化且未独立核验 |
| `AMOUNT_ABOVE_HISTORICAL_MAX` | 金额超过历史最大订单一定倍数 |

原有金额突增、Z-score、小单转大单、高频下单、付款方式/国家/地址/品类变化、资料变更后大额下单、拆单、不良履约和新客户大额订单规则继续保留。

交易风险等级由确定性规则最高严重度主导；多规则仅在该等级上限内有限增加风险分，避免无意义的黑箱加权。

## Risk Exposure

```text
当前敞口 = max(0, max(已发货货值, 已交付货值) - 已确认收款 - 已验证保障)
预计最大敞口 = max(0, 计划发货货值 - 发货前计划到账 - 已验证保障)
```

约束：

- 覆盖额最多抵扣可能暴露货值，敞口永不为负；
- 未验证保险/担保不抵扣；
- 保障币种与订单币种不一致时拒绝计算，不猜汇率；
- 条款中没有明确付款金额时，才用订单金额 × 定金比例作为计划到账回退。

## Evidence Completeness

必需证据由交易金额、首次/有限合作、账期和缓释方式动态生成。身份、合同、付款主体和付款条款是关键证据；完整度按权重计算。即使提交大量普通证据，关键证据缺失仍会保留在 `critical_missing`。

证据只保存受控文件引用、摘要、校验和、采集/核验状态与时间，不在 Agent 会话保存敏感原文。

## Risk Mitigation

保险、担保、信用证、平台保障和托管只有在 `verified=true` 且币种一致时才可抵扣。服务输出真实 `coverage_amount` 与 `coverage_ratio`，不制造抽象“缓释评分”。分批发货属于交易条件建议，不凭空折算成保障金额。

## Credit Terms

条款服务结合 Trust、Transaction Risk、Exposure、Evidence 和 Mitigation，输出：

- 状态，如 `RECOMMENDED_WITH_ADJUSTMENTS`；
- 建议最低定金比例；
- 建议最长账期；
- 分批发货、付款节点和核验建议；
- `human_decision_required=true`。

这些是建议，不会自动修改 `transactions` 或 `transaction_terms`。

## Isolation Forest 的定位

Isolation Forest 保留 14 维共享特征、版本化模型和统计降级，但输出被明确标记为 `signal_role=auxiliary_only`。即使 `anomaly_score` 很高，只要没有确定性规则命中，也不能单独产生 HIGH 或 CRITICAL 交易风险。

## 评估与模拟

- `POST /api/decisions/evaluate`：评估草稿、客户或正式交易；默认不保存快照，`persist_snapshot=true` 时保存不可变决策快照。
- `POST /api/decisions/simulate`：合并允许的条款调整后重新计算，返回 before/after 和敞口、定金、账期、决策状态变化；始终 `persisted=false`。

所有计算均可脱离 LLM 单独测试。
