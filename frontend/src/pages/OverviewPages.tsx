import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Bot, Boxes, Clock3, FileCheck2, Globe2, Handshake, MessageSquareText, Play, ShieldCheck, Sparkles, TrendingUp, WandSparkles } from 'lucide-react'
import { safeGet } from '../api/client'
import { dashboard as fallbackDashboard } from '../data/fallback'
import { Card, DemoNotice, MetricCard, PageHeader, ProgressBar } from '../components/ui'
import { DonutChart, FunnelView, HorizontalBars, TimeCompareChart, TrendChart } from '../components/charts'

const flow = [
  ['产品设计', WandSparkles], ['数字展台', Boxes], ['AI接待', Bot], ['客户询盘', MessageSquareText],
  ['智能报价', FileCheck2], ['风险评估', ShieldCheck], ['订单履约', TrendingUp], ['信用资产', Handshake],
] as const

export function StoryPage() {
  const navigate = useNavigate()
  return <div className="story-page">
    <section className="hero card">
      <div className="hero-grid-bg" />
      <div className="hero-copy">
        <div className="hero-kicker"><span className="pulse-dot" />义乌国际贸易数字化社会实践成果</div>
        <h1>Yiwu AI<br /><span>Trade Copilot</span></h1>
        <h2>义乌AI国际贸易智能体</h2>
        <p className="hero-subtitle">从交易效率提升到数字信任重构</p>
        <p className="hero-value">AI不仅帮助义乌商户卖得更快，<strong>也帮助他们卖得更放心。</strong></p>
        <div className="hero-actions"><button className="btn btn-primary btn-lg" onClick={() => navigate('/roadshow')}><Play size={18} />开始 8 分钟路演</button><button className="btn btn-secondary btn-lg" onClick={() => navigate('/dashboard')}>进入系统演示<ArrowRight size={18} /></button></div>
        <DemoNotice>页面指标均为基于调研假设的 Demo 模拟测算，并非真实统计结论。</DemoNotice>
      </div>
      <div className="hero-orbit" aria-label="AI数字信任概念图">
        <div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" />
        <div className="trust-core"><ShieldCheck size={42} /><strong>AI数字信任</strong><span>可量化 · 可解释</span></div>
        <div className="orbit-node node-a"><Globe2 size={18} />跨境触达</div>
        <div className="orbit-node node-b"><Bot size={18} />智能响应</div>
        <div className="orbit-node node-c"><FileCheck2 size={18} />风险护航</div>
        <div className="trust-score-float"><span>TRUST SCORE</span><strong>86</strong><small>/ 100</small></div>
      </div>
    </section>

    <section className="story-timeline">
      <div className="timeline-intro"><span>义乌贸易信任演化</span><h2>从关系网络，到数字效率，再到AI数字信任</h2></div>
      <div className="era-grid">
        <article className="era-card past"><span className="era-index">01 · 过去</span><h3>人与人建立信任</h3><strong>莫名其妙</strong><p>靠面对面、熟人介绍、长期合作与口碑，信任深厚但扩张缓慢。</p><div className="era-tag">人际信任</div></article>
        <div className="era-arrow"><ArrowRight /></div>
        <article className="era-card present"><span className="era-index">02 · 现在</span><h3>数字工具提高效率</h3><strong>无中生有</strong><p>AI生图、翻译、平台、短视频让产品更快触达全球，但身份与履约风险仍难判断。</p><div className="era-tag">数字效率</div></article>
        <div className="era-arrow"><ArrowRight /></div>
        <article className="era-card future"><span className="era-index">03 · 未来</span><h3>AI重构数字信任</h3><strong>点石成金</strong><p>把碎片化工具连成完整闭环，让每次交易沉淀为可量化、可解释的信用资产。</p><div className="era-tag">AI数字信任</div></article>
      </div>
      <div className="finding-strip"><Sparkles size={20} /><div><strong>核心调研结论</strong><span>AI正在显著提升贸易效率，但客户身份、付款与合同风险仍构成线上交易的“信任缺口”。</span></div></div>
    </section>

    <section>
      <div className="section-title"><span>END-TO-END COPILOT</span><h2>一条贯穿贸易全链路的智能闭环</h2><p>从灵感到履约，每一步都在沉淀数据，每一笔数据都在形成信用资产。</p></div>
      <div className="flow-track">{flow.map(([label, Icon], index) => <div className="flow-item" key={label}><div><Icon size={20} /></div><span>{label}</span>{index < flow.length - 1 && <ArrowRight className="flow-arrow" size={16} />}</div>)}</div>
    </section>

    <section className="impact-highlight">
      <div className="section-title align-left"><span>DEMO IMPACT</span><h2>让效率提升被看见，让风险变化被解释</h2></div>
      <div className="impact-metrics">
        <MetricCard label="AI平均响应时间" value={8} suffix=" 秒" change="人工约15分钟" tone="cyan" icon={<Clock3 size={18} />} />
        <MetricCard label="报价单生成时间" value={30} suffix=" 秒" change="人工约20分钟" tone="blue" icon={<FileCheck2 size={18} />} />
        <MetricCard label="高风险询盘识别率" value={85} suffix="%" change="规则模型模拟值" tone="violet" icon={<ShieldCheck size={18} />} />
        <MetricCard label="商户日均节省时间" value={3.2} suffix=" 小时" change="调研假设估算" tone="green" icon={<TrendingUp size={18} />} />
      </div>
    </section>
  </div>
}

export function DashboardPage() {
  const [data, setData] = useState<any>(fallbackDashboard)
  useEffect(() => { safeGet('/dashboard', fallbackDashboard).then(result => setData(result.data)) }, [])
  return <div>
    <PageHeader eyebrow="AI BOSS COCKPIT" title="AI老板驾驶舱" description="用一块屏幕掌握询盘、成交、利润与交易风险。" actions={<><button className="btn btn-secondary">导出日报</button><button className="btn btn-primary"><Sparkles size={16} />AI经营简报</button></>} />
    <DemoNotice>今日经营数据为 Demo 模拟测算，重点展示指标体系与决策逻辑。</DemoNotice>
    <div className="metric-grid dashboard-metrics">{data.metrics.map((item: any) => <MetricCard key={item.label} {...item} />)}</div>
    <div className="dashboard-grid">
      <Card className="chart-card span-2" title="最近7天询盘趋势" action={<span className="chart-caption">较上周 +18.6%</span>}><div className="chart-box tall"><TrendChart data={data.inquiry_trend} /></div></Card>
      <Card className="chart-card" title="客户来源分布"><div className="chart-box tall"><DonutChart data={data.sources} /></div></Card>
      <Card className="chart-card" title="客户国家 / 地区 TOP 5"><div className="chart-box"><HorizontalBars data={data.countries} /></div></Card>
      <Card className="chart-card" title="询盘转化漏斗"><div className="chart-box"><FunnelView data={data.funnel} /></div></Card>
      <Card className="chart-card" title="风险等级分布"><div className="chart-box"><DonutChart data={data.risks} /></div></Card>
      <Card className="chart-card span-2" title="AI带来的时间节省" action={<span className="chart-caption">单位：分钟/次</span>}><div className="chart-box"><TimeCompareChart data={data.time_saving} /></div></Card>
      <Card className="chart-card" title="产品热度排名"><div className="rank-list">{data.products.map((item: any, index: number) => <div className="rank-row" key={item.name}><span className="rank-num">{index + 1}</span><div><strong>{item.name}</strong><ProgressBar value={item.heat} tone={index === 0 ? 'green' : 'blue'} /></div><b>{item.heat}</b></div>)}</div></Card>
      <Card className="chart-card" title="订单状态分布"><div className="chart-box"><DonutChart data={data.order_status} /></div></Card>
    </div>
  </div>
}

