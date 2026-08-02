import type { Customer, Inquiry, Order, Product } from '../types'

export const products: Product[] = [
  { id: 1, name: 'EcoPulse环保保温杯', category: '家居日用', sku: 'YAT-CUP-001', description: '304食品级不锈钢、BPA-free杯盖，支持多语言包装与小批量定制。', price: 12.8, cost: 7.6, moq: 500, stock: 8600, lead_days: 18, target_markets: '法国,德国,西班牙', tags: '环保,热销,可定制', multilingual_points: 'Sustainable · BPA-free · Emballage français', model_config: '{"shape":"cylinder","color":"#31c6a4"}', popularity: 96 },
  { id: 2, name: 'LumiNest氛围灯', category: '家居装饰', sku: 'YAT-LMP-012', description: 'USB-C充电、三档色温，可定制礼盒与Logo。', price: 8.9, cost: 4.7, moq: 300, stock: 5300, lead_days: 15, target_markets: '美国,英国,阿联酋', tags: '家居,礼品,新品', multilingual_points: 'Portable · Warm light · Gift ready', model_config: '{"shape":"sphere","color":"#ffb45c"}', popularity: 89 },
  { id: 3, name: 'FlexPack折叠旅行包', category: '箱包', sku: 'YAT-BAG-023', description: '防泼水再生面料，折叠体积仅为普通旅行包的1/5。', price: 6.6, cost: 3.3, moq: 800, stock: 12000, lead_days: 22, target_markets: '美国,俄罗斯,巴西', tags: '旅行,轻量,再生材料', multilingual_points: 'Foldable · Water resistant · Recycled', model_config: '{"shape":"box","color":"#5b8cff"}', popularity: 84 },
  { id: 4, name: 'MiniChef硅胶厨具套装', category: '厨具', sku: 'YAT-KIT-034', description: '食品级硅胶六件套，耐温230℃，适合电商礼盒。', price: 9.5, cost: 5.2, moq: 600, stock: 7400, lead_days: 20, target_markets: '法国,加拿大,澳大利亚', tags: '厨房,套装,礼盒', multilingual_points: 'Food grade · Six pieces · Color custom', model_config: '{"shape":"cone","color":"#e97988"}', popularity: 78 },
  { id: 5, name: 'SolarGo便携太阳能灯', category: '户外用品', sku: 'YAT-SOL-045', description: 'IP65防水、太阳能与Type-C双充电，适合户外及应急使用。', price: 14.2, cost: 8.4, moq: 400, stock: 3900, lead_days: 25, target_markets: '南非,沙特,墨西哥', tags: '太阳能,户外,应急', multilingual_points: 'Solar · IP65 · Emergency ready', model_config: '{"shape":"cylinder","color":"#ffd166"}', popularity: 92 },
]

export const customers: Customer[] = [
  { id: 1, company: 'Maison Verte SAS', contact: 'Claire Martin', country: '法国', email: 'claire@maisonverte.fr', registered_years: 11, historical_orders: 18, historical_amount: 286000, source: '展会老客', intent_level: '高', risk_level: '低风险', credit_score: 93, last_contact: '今天 09:24', tags: '长期客户,环保品类' },
  { id: 2, company: 'Pacific Retail LLC', contact: 'Ethan Walker', country: '美国', email: 'ethan@pacificretail.com', registered_years: 3, historical_orders: 2, historical_amount: 32800, source: '数字展台', intent_level: '高', risk_level: '中风险', credit_score: 72, last_contact: '今天 10:18', tags: '批量采购,议价敏感' },
  { id: 3, company: 'Nova Import Group', contact: 'Alex Novak', country: '波兰', email: 'novaimport@outlook.com', registered_years: 1, historical_orders: 0, historical_amount: 0, source: '社交媒体', intent_level: '中', risk_level: '高风险', credit_score: 42, last_contact: '昨天 18:42', tags: '新客户,付款异常' },
  { id: 4, company: 'Global Fast Trade', contact: 'Samir K.', country: '阿联酋', email: 'fasttrade2026@gmail.com', registered_years: 0, historical_orders: 0, historical_amount: 0, source: '陌生邮件', intent_level: '高', risk_level: '极高风险', credit_score: 16, last_contact: '今天 11:05', tags: '身份存疑,货到付款,异常催促' },
  { id: 5, company: 'Mercado Soluciones', contact: 'Lucía Torres', country: '西班牙', email: 'lucia@mercadosol.es', registered_years: 6, historical_orders: 7, historical_amount: 91400, source: '跨境平台', intent_level: '中', risk_level: '低风险', credit_score: 87, last_contact: '3天前', tags: '复购,家居用品' },
]

export const inquiries: Inquiry[] = [
  { id: 1, inquiry_no: 'INQ-20260802-001', customer: 'Maison Verte SAS', country: '法国', product: 'EcoPulse环保保温杯', quantity: 2200, target_price: 11.9, payment_method: 'T/T 30/70', destination: 'Le Havre, France', expected_delivery: '2026-09-25', status: '已报价', intent_score: 91, risk_score: 12, ai_summary: '法国长期客户寻找环保保温杯，重视FSC包装与法语标签。', recommended_action: '发送样品确认并锁定生产排期' },
  { id: 2, inquiry_no: 'INQ-20260802-002', customer: 'Pacific Retail LLC', country: '美国', product: 'FlexPack折叠旅行包', quantity: 5000, target_price: 5.8, payment_method: 'L/C', destination: 'Los Angeles, USA', expected_delivery: '2026-10-10', status: '跟进中', intent_score: 86, risk_score: 38, ai_summary: '美国采购商计划大批量采购旅行包，目标价较低，可通过标准包装优化。', recommended_action: '提供阶梯报价' },
  { id: 3, inquiry_no: 'INQ-20260801-009', customer: 'Nova Import Group', country: '波兰', product: 'LumiNest氛围灯', quantity: 15000, target_price: 7.2, payment_method: '个人账户转账', destination: 'Warsaw, Poland', expected_delivery: '尽快', status: '风险复核', intent_score: 67, risk_score: 71, ai_summary: '首单金额显著偏高，要求个人账户结算且资料不完整。', recommended_action: '暂停报价，完成企业与地址核验' },
  { id: 4, inquiry_no: 'INQ-20260802-004', customer: 'Global Fast Trade', country: '阿联酋', product: 'SolarGo便携太阳能灯', quantity: 30000, target_price: 10, payment_method: '货到付款 COD', destination: '地址待定', expected_delivery: '立即发货', status: '已拦截', intent_score: 74, risk_score: 92, ai_summary: '客户拒绝公司验证，要求超大首单货到付款并多次催促。', recommended_action: '停止自动推进并提交人工反欺诈复核' },
  { id: 5, inquiry_no: 'INQ-20260731-018', customer: 'Mercado Soluciones', country: '西班牙', product: 'MiniChef硅胶厨具套装', quantity: 1200, target_price: 8.8, payment_method: 'T/T 40/60', destination: 'Valencia, Spain', expected_delivery: '2026-09-18', status: '待确认', intent_score: 73, risk_score: 19, ai_summary: '复购客户新增厨具品类，关注欧盟食品接触材料说明。', recommended_action: '发送合规资料与西语包装样稿' },
]

export const orders: Order[] = [
  { id: 1, order_no: 'ORD-2026-0801', customer: 'Maison Verte SAS', product: 'EcoPulse环保保温杯', quantity: 2200, amount: 27500, profit: 8120, payment_status: '已收预付款', production_status: '生产中', logistics_status: '待订舱', risk_status: '低风险', expected_delivery: '2026-09-25', progress: 48 },
  { id: 2, order_no: 'ORD-2026-0733', customer: 'Mercado Soluciones', product: 'MiniChef硅胶厨具套装', quantity: 900, amount: 8550, profit: 2640, payment_status: '已付清', production_status: '质检中', logistics_status: '待发货', risk_status: '低风险', expected_delivery: '2026-08-22', progress: 72 },
  { id: 3, order_no: 'ORD-2026-0718', customer: 'Pacific Retail LLC', product: 'FlexPack折叠旅行包', quantity: 3000, amount: 19600, profit: 4980, payment_status: '待尾款', production_status: '已完成', logistics_status: '运输中', risk_status: '中风险', expected_delivery: '2026-08-30', progress: 84 },
  { id: 4, order_no: 'ORD-2026-0692', customer: 'Maison Verte SAS', product: 'LumiNest氛围灯', quantity: 1000, amount: 8900, profit: 2450, payment_status: '已付清', production_status: '已完成', logistics_status: '已到港', risk_status: '低风险', expected_delivery: '2026-08-05', progress: 96 },
]

export const dashboard = {
  metrics: [
    { label: '今日询盘', value: 42, change: '+18%', tone: 'blue' }, { label: '有效询盘', value: 31, change: '73.8%', tone: 'cyan' },
    { label: '高意向客户', value: 12, change: '+3', tone: 'green' }, { label: '今日订单', value: 8, change: '+14%', tone: 'violet' },
    { label: '预计成交金额', value: 128600, prefix: '¥', change: '+22%', tone: 'gold' }, { label: '预计利润', value: 38600, prefix: '¥', change: '30.0%', tone: 'green' },
    { label: '风险订单', value: 3, change: '已拦截2笔', tone: 'red' }, { label: 'AI自动处理率', value: 72, suffix: '%', change: '+8pp', tone: 'cyan' },
    { label: '平均回复', value: 8, suffix: '秒', change: '原15分钟', tone: 'blue' }, { label: '平均风险分', value: 34, suffix: '/100', change: '中低风险', tone: 'violet' },
  ],
  inquiry_trend: [{ day: '7/27', inquiries: 24, valid: 17 }, { day: '7/28', inquiries: 29, valid: 22 }, { day: '7/29', inquiries: 27, valid: 19 }, { day: '7/30', inquiries: 35, valid: 25 }, { day: '7/31', inquiries: 33, valid: 26 }, { day: '8/1', inquiries: 38, valid: 29 }, { day: '8/2', inquiries: 42, valid: 31 }],
  sources: [{ name: '数字展台', value: 36 }, { name: '跨境平台', value: 27 }, { name: '社交媒体', value: 18 }, { name: '展会转介', value: 12 }, { name: '老客复购', value: 7 }],
  countries: [{ name: '法国', value: 28 }, { name: '美国', value: 24 }, { name: '西班牙', value: 17 }, { name: '阿联酋', value: 13 }, { name: '德国', value: 11 }],
  funnel: [{ name: '访问展台', value: 1280 }, { name: 'AI对话', value: 426 }, { name: '有效询盘', value: 188 }, { name: '已报价', value: 96 }, { name: '成交订单', value: 41 }],
  risks: [{ name: '低风险', value: 54, color: '#2fd1a4' }, { name: '中风险', value: 28, color: '#f4bd50' }, { name: '高风险', value: 13, color: '#ff865f' }, { name: '极高风险', value: 5, color: '#f4576c' }],
  time_saving: [{ task: '客户回复', manual: 15, ai: 0.13 }, { task: '生成报价', manual: 20, ai: 0.5 }, { task: '询盘总结', manual: 12, ai: 0.3 }, { task: '风险初筛', manual: 18, ai: 0.8 }],
  products: [{ name: 'EcoPulse保温杯', heat: 96 }, { name: 'SolarGo太阳能灯', heat: 92 }, { name: 'LumiNest氛围灯', heat: 89 }, { name: 'FlexPack旅行包', heat: 84 }],
  order_status: [{ name: '待付款', value: 8 }, { name: '生产中', value: 16 }, { name: '运输中', value: 11 }, { name: '已完成', value: 28 }],
}

export const scenarios = [
  { code: 'A', title: '法国采购商寻找环保保温杯', description: '多语言推荐、环保卖点与高意向识别', language: 'fr', risk_hint: '低风险', messages: [{ role: 'assistant', content: 'Bonjour! Je suis votre assistant commercial IA à Yiwu.' }, { role: 'user', content: 'We need eco-friendly insulated bottles with French packaging for 2,000 units.' }] },
  { code: 'B', title: '美国采购商大批量议价', description: '阶梯报价、利润护栏与议价建议', language: 'en', risk_hint: '中风险', messages: [{ role: 'assistant', content: 'Welcome! I can help with wholesale pricing and delivery options.' }, { role: 'user', content: 'We need 5,000 travel bags, but your price must be lower.' }] },
  { code: 'C', title: '高风险货到付款客户', description: '拒绝核验、异常付款与风险拦截', language: 'en', risk_hint: '极高风险', messages: [{ role: 'assistant', content: 'Before a large first order, we complete a quick company verification.' }, { role: 'user', content: 'Ship 30,000 units COD today. I refuse to provide company information.' }] },
]

export const fallbackMap: Record<string, unknown> = {
  '/dashboard': dashboard,
  '/products': products,
  '/customers': customers,
  '/inquiries': inquiries,
  '/orders': orders,
  '/demo/scenarios': scenarios,
}

