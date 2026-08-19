# 数据字典

## 核心与兼容表

| 表 | 关键字段 | 用途 |
|---|---|---|
| `merchants` | id, name, contact | 商户租户根实体 |
| `customers` | merchant_id, company_name, country, identity_verified, blacklist_status | 客户档案和人工状态 |
| `transactions` | merchant_id, customer_id, order_number, amount, payment/refund/dispute/overdue | 正式交易与履约事实 |
| `credit_score_history` | customer_id, total_score, five subscores, confidence_level, rule_version | legacy 信用分历史，仅作参考 |
| `risk_rule_config` | rule_code, threshold_config, severity, enabled, version | 可配置规则元数据 |
| `risk_events` | merchant_id, customer_id, order_id, score, rules, evidence, status | 兼容预警与人工处置闭环 |
| `audit_logs` | merchant_id, object_type, object_id, action, before/after, actor | 关键操作审计 |

## 交易决策表

| 表 | 关键字段 | 用途 |
|---|---|---|
| `transaction_terms` | merchant_id, transaction_id, credit_days, due_date, deposit, payer/account/contract, planned shipping/payment | 一笔正式交易的合同与授信条款；transaction_id 唯一 |
| `transaction_timeline_events` | merchant_id, transaction_id, event_type/time, amount, verified | 付款、发货、交付、到期、延期和纠纷事实 |
| `transaction_evidence_items` | merchant_id, transaction_id, type, status, verified, controlled reference, summary, checksum | 证据元数据，不保存敏感原文 |
| `transaction_mitigations` | merchant_id, transaction_id, type, verified, coverage amount/currency, validity | 保险、担保、信用证等缓释事实 |
| `customer_trust_snapshots` | merchant_id, customer_id, cooperation, counts, amounts, payment/overdue/refund/dispute, trust/confidence, missing | Customer Trust v2 快照 |
| `transaction_decision_snapshots` | merchant_id, customer_id, transaction_id, status, decision_data, version, calculated_at | 可选的不可变交易决策快照 |
| `transaction_evidence_packages` | merchant_id, transaction_id, package_data, html_content, checksum, generated_at | JSON/HTML 证据包快照 |

## Agent 与知识库

| 表 | 关键字段 | 用途 |
|---|---|---|
| `agent_conversations` | merchant_id, user_id, conversation_id, title, customer_id, timestamps | 脱敏会话索引 |
| `agent_messages` | conversation_id, role, content, tool_calls, created_at | 脱敏消息和最小 Tool 元数据 |
| `agent_decision_contexts` | merchant_id, user_id, conversation_id, customer/transaction, version, context, required/missing, completeness, next question | 与聊天记录分离的多轮结构化决策状态 |
| `knowledge_base` | title, content, embedding, category, created_at | 非结构化知识块；PostgreSQL 使用 pgvector，SQLite 测试使用 JSON |

## 字段语义约定

- 金额必须与 `currency` 一起解释；没有明确汇率快照时禁止跨币种抵扣。
- 比例使用 0–1，例如 20% 存为 `0.2`。
- `verified` 表示已通过业务流程核验，不等同于 Agent 或模型推断。
- `on_time_payment_rate=null` 表示缺少明确到期依据，不应展示为 100%。
- `current_exposure` 与 `projected_max_exposure` 最小为 0。
- `missing_fields` 明确记录信息不足，防止将未知当作低风险。
- 时间按无时区 UTC 语义存储；生产应使用统一数据库时区并在展示层本地化。

## 隔离与隐私

除全局规则配置和知识库外，新增业务表均包含 `merchant_id`。Agent Context 还以 `(merchant_id, user_id, conversation_id)` 唯一。证据包不包含客户邮箱、电话、完整付款账号或聊天原文；摘要在导出前做最低限度脱敏。

迁移 `20260819_0004_transaction_decision.py` 创建上述 P0/P1 表并兼容 PostgreSQL 与 SQLite 测试环境。
