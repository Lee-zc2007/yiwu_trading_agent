# 改造验收报告

## 验收范围

本次改造在原有 MVP 上增加交易授信与风险决策能力，保留客户、交易、预警、审计、legacy 信用分、旧订单分析 API、Mock/LLM 和 RAG 能力，没有重新设计整个系统。

## P0 功能

- [x] 删除硬编码场景页面、后端路由、服务、Schema 和脚本引用；普通业务数据与 `/api/risk/analyze-order` 保留。
- [x] 新增交易条款、时间线、证据、缓释、Customer Trust、Decision Context 和决策快照模型及 Alembic 迁移。
- [x] Customer Trust v2 不再用“订单 + 7 天”伪造到期日；到期依据未知时按期率为 unknown。
- [x] Risk Exposure 支持当前/预计敞口、保障上限、未核验保障不抵扣和币种检查。
- [x] Evidence Completeness 支持加权必需证据与 `critical_missing`。
- [x] Risk Mitigation 只计算真实已核验覆盖，不产生虚构缓释分。
- [x] Credit Terms 输出可执行建议并强制人工决策。
- [x] rules_v2 新增首次授信、低定金、长账期、账期延长、尾款延后、付款主体不一致、账户变化和超历史最大额规则。
- [x] Isolation Forest 降为辅助信号，不能单独生成 HIGH/CRITICAL。
- [x] `POST /api/decisions/evaluate` 与 `/simulate` 已实现；模拟不写正式交易。
- [x] Agent Decision Context 支持抽取、合并、主动追问、Tool 调用、证据回答和调整前后比较。
- [x] `/agent`、`/risk-check`、工作台和客户详情已改为交易决策视角。

## P1 功能

- [x] Transaction Evidence Package 包含客户、订单、合同、付款、发货、验货、脱敏沟通摘要、延期、纠纷、时间线、缓释和当前决策。
- [x] 支持结构化 JSON 和自包含 HTML；使用 SHA-256 校验和并记录生成审计。
- [x] 未引入项目原本不存在的复杂 PDF 依赖。

## API 验收

- [x] 客户信任：`GET /api/customers/{id}/trust`
- [x] 决策评估/模拟：`POST /api/decisions/evaluate|simulate`
- [x] 条款：`GET/PUT /api/transactions/{id}/terms`
- [x] 证据：`GET/POST /api/transactions/{id}/evidence`
- [x] 缓释：`GET/POST /api/transactions/{id}/mitigations`
- [x] 敞口、决策、时间线：对应交易子资源 GET 接口
- [x] 证据包：生成与 JSON/HTML 读取接口
- [x] Agent：`POST /api/agent/chat` 与会话历史接口

## 自动化测试覆盖

- [x] 50000 USD、已确认/计划到账 10000，预计敞口 40000。
- [x] coverage 大于暴露货值时敞口不为负。
- [x] 未核验保险不抵扣。
- [x] 普通证据再多也不能掩盖关键证据缺失。
- [x] 首次合作 3 万美元、45 天账期时 Agent 主动追问定金。
- [x] 后续输入“20%”正确合并为 `deposit_ratio=0.2`。
- [x] “提高到 40%”调用模拟并确认数据库正式交易未变化。
- [x] 高 Isolation Forest 异常度不能单独产生 HIGH/CRITICAL。
- [x] decision、terms、evidence、mitigation、timeline、context、evidence package 均有商户隔离测试。
- [x] 证据包 JSON、HTML、校验和、隐私字段与租户隔离测试。

## 最终对话验收标准

```text
自然语言订单 → 抽取条件 → 缺失字段 → 主动追问 → 合并补充
→ Customer Trust → Transaction Risk → Risk Exposure
→ Evidence Completeness → Risk Mitigation → Credit Terms → 引用证据回答
```

调整意图必须走：

```text
modify_transaction_terms → 更新当前 Context
→ simulate_transaction_adjustment → before / after → persisted=false
```

## 交付前命令

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

本文件的勾选表示功能和测试已纳入实现；最终通过数量和生产构建结果以交付回复中的本次实际终端结果为准。

## 已知边界

- 演示环境以请求头模拟商户/用户，生产需补充真实认证和权限。
- Customer Trust 质量取决于明确的到期、付款、退款、纠纷和拒付数据。
- RAG 本地 hash embedding 仅用于无外部服务演示，生产应接真实 embedding、文档授权和召回评测。
- 系统不自动审批授信，不把异常等同于欺诈，也不自动执行暂停发货或黑名单动作。
