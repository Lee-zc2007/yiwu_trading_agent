# REST API 速查

启动后访问 `http://localhost:8000/docs` 查看可交互 Swagger 文档。

| 模块 | 方法与路径 | 说明 |
|---|---|---|
| 系统 | `GET /api/health` | 健康检查与运行模式 |
| 驾驶舱 | `GET /api/dashboard` | 指标与全部图表数据 |
| 产品 | `GET/POST /api/products` | 产品列表与创建 |
| 产品 | `GET /api/products/{id}` | 产品详情 |
| AI设计 | `POST /api/products/generate` | 生成产品概念 |
| AI销售 | `POST /api/ai/chat` | 多语言规则对话 |
| 客户 | `GET /api/customers` | 客户列表 |
| 客户 | `GET /api/customers/{id}` | 客户、询盘和风险档案 |
| 询盘 | `GET/POST /api/inquiries` | 询盘列表与创建 |
| 询盘 | `GET/PATCH /api/inquiries/{id}` | 询盘详情与状态更新 |
| 报价 | `POST /api/quotes/calculate` | 报价实时计算 |
| 报价 | `GET/POST /api/quotes` | 历史报价与保存 |
| 报价 | `POST /api/quotes/preview/pdf` | 预览参数生成 PDF |
| 报价 | `GET /api/quotes/{id}/pdf` | 下载历史报价 PDF |
| 风险 | `POST /api/risk/evaluate` | 规则化风险评估 |
| 风险 | `GET /api/risk/customers/{id}` | 客户风险档案 |
| 合同 | `POST /api/contracts/analyze` | 合同规则审核 |
| 订单 | `GET /api/orders` | 订单列表 |
| 订单 | `GET /api/orders/{id}` | 订单详情与时间轴 |
| 物流 | `POST /api/logistics/recommend` | 海运/铁路/空运比较 |
| 售后 | `GET /api/after-sales` | 售后与复购数据 |
| 效果 | `POST /api/analytics/impact` | 使用前后效果模拟 |
| 调研 | `GET /api/research/metrics` | 调研占位指标与成果 |
| 演示 | `POST /api/demo/reset` | 重置演示数据库 |
| 演示 | `GET /api/demo/scenarios` | 内置路演对话场景 |

所有写入请求均经过 Pydantic 字段类型、范围和长度校验。

