# 数据字典

| 表 | 关键字段 | 用途 |
|---|---|---|
| merchants | id, name, contact | 商户租户根实体 |
| customers | merchant_id, company_name, country, identity_verified, blacklist_status | 外商档案与人工状态 |
| transactions | customer_id, order_number, amount, payment/refund/dispute/overdue, shipping | 交易与履约事实 |
| credit_score_history | customer_id, total_score, 五个子分, confidence_level, rule_version | 可追溯信用评分历史 |
| agent_conversations | merchant_id, user_id, conversation_id, title, customer_id, created_at, updated_at | 按商户和用户隔离的 Agent 会话；title 入库前脱敏 |
| agent_messages | conversation_id, role, content, tool_calls, created_at | 脱敏后的消息和安全 Tool 调用元数据，不保存 Tool 完整结果 |
| risk_rule_config | rule_code, threshold_config, severity, enabled, version | 风险规则配置 |
| risk_events | customer_id, order_id, risk_score, triggered_rules, evidence, status | 风险证据与人工处置闭环 |
| audit_logs | object_type, object_id, action, before_data, after_data, actor | 关键变更审计 |

金额均同时保存 `currency`，示例数据默认 USD。时间在 API 层转为无时区 UTC 语义存储；生产应统一使用数据库时区字段并在展示层本地化。
