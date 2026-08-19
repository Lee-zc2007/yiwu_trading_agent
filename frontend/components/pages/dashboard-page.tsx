'use client'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowRight, CircleDollarSign, Clock3, FileWarning, HandCoins, SlidersHorizontal, WalletCards } from 'lucide-react'
import { api } from '@/lib/api'
import type { Dashboard } from '@/lib/types'
import { money } from '@/lib/utils'
import { PageHeader } from '@/components/page-header'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge, riskLabel } from '@/components/ui/badge'
import { Chart } from '@/components/chart'
import { ErrorState, Loading } from '@/components/states'

const metricMeta=[
  ['unsecured_exposure','未保障风险敞口',WalletCards,'money'],
  ['high_risk_exposure','高风险敞口',AlertTriangle,'money'],
  ['pending_credit_orders','待处理授信订单',HandCoins,'笔'],
  ['credit_order_amount','账期订单金额',CircleDollarSign,'money'],
  ['evidence_missing_orders','证据缺失订单',FileWarning,'笔'],
  ['payments_due_soon','即将到期尾款',Clock3,'笔'],
  ['terms_adjustment_orders','建议调整条件',SlidersHorizontal,'笔'],
] as const
export function DashboardPage(){const query=useQuery({queryKey:['dashboard'],queryFn:()=>api<Dashboard>('/api/risk/dashboard')});if(query.isLoading)return <Loading/>;if(query.error)return <ErrorState message={query.error.message}/>;const data=query.data!;const lineOption={tooltip:{trigger:'axis'},legend:{data:['全部预警','高风险'],bottom:0},grid:{left:35,right:15,top:20,bottom:45},xAxis:{type:'category',data:data.risk_trend.map(i=>i.date),axisLine:{lineStyle:{color:'#dbe5e4'}}},yAxis:{type:'value',minInterval:1,splitLine:{lineStyle:{color:'#edf2f2'}}},series:[{name:'全部预警',type:'line',smooth:true,data:data.risk_trend.map(i=>i.alerts),lineStyle:{color:'#0d9488',width:3},itemStyle:{color:'#0d9488'},areaStyle:{color:'rgba(13,148,136,.08)'}},{name:'高风险',type:'line',smooth:true,data:data.risk_trend.map(i=>i.high),lineStyle:{color:'#e5593f',width:2},itemStyle:{color:'#e5593f'}}]};const pieOption={tooltip:{trigger:'item'},legend:{bottom:0},series:[{type:'pie',radius:['48%','70%'],center:['50%','45%'],label:{show:false},data:data.risk_distribution.map(item=>({...item,itemStyle:{color:{low:'#20a77a',medium:'#e8a23b',high:'#ee7b3d',critical:'#d94841'}[item.name]}}))}]};return <div><PageHeader eyebrow="CREDIT EXPOSURE OPERATIONS" title="交易风险与敞口总览" description="优先关注未保障敞口、账期交易、证据缺失和需要调整交易条件的订单。" actions={<Link href="/risk-check" className="inline-flex h-10 items-center gap-2 rounded-lg bg-teal-600 px-4 text-sm font-semibold text-white">发起交易决策<ArrowRight size={15}/></Link>}/>
  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-7">{metricMeta.map(([key,label,Icon,suffix])=><Card key={key} className="p-4"><div className="flex items-start justify-between"><span className="text-[10px] font-semibold text-slate-500">{label}</span><Icon size={16} className="text-teal-600"/></div><strong className="mt-3 block text-xl tracking-tight">{suffix==='money'?money(data.metrics[key]):`${data.metrics[key]}${suffix}`}</strong><p className="mt-1 text-[9px] text-slate-400">确定性业务口径</p></Card>)}</div>
  <div className="mt-4 grid gap-4 xl:grid-cols-[1.5fr_.8fr_.9fr]"><Card><CardHeader><div><h3 className="text-sm font-bold">近 7 日风险趋势</h3><p className="mt-1 text-[10px] text-slate-400">按预警创建时间统计</p></div></CardHeader><CardContent><Chart option={lineOption}/></CardContent></Card><Card><CardHeader><div><h3 className="text-sm font-bold">风险等级分布</h3><p className="mt-1 text-[10px] text-slate-400">当前全部风险事件</p></div></CardHeader><CardContent><Chart option={pieOption}/></CardContent></Card><Card><CardHeader><h3 className="text-sm font-bold">高风险外商排行</h3><Link href="/customers" className="text-[10px] text-teal-600">查看全部</Link></CardHeader><div className="divide-y divide-slate-100">{data.high_risk_customers.length?data.high_risk_customers.map((item,index)=><Link key={item.id} href={`/customers/${item.id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-slate-50"><span className="grid size-7 place-items-center rounded-lg bg-slate-100 text-[10px] font-bold">{index+1}</span><div className="min-w-0 flex-1"><strong className="block truncate text-xs">{item.company_name}</strong><span className="text-[9px] text-slate-400">{item.country} · {item.risk_level}</span></div><strong className="text-sm text-red-600">{item.score.toFixed(0)}</strong></Link>):<p className="p-5 text-xs text-slate-400">当前没有信用分低于 60 的外商</p>}</div></Card></div>
  <Card className="mt-4"><CardHeader><div><h3 className="text-sm font-bold">最新风险预警</h3><p className="mt-1 text-[10px] text-slate-400">按时间倒序展示，点击进入处置中心</p></div><Link href="/alerts" className="text-xs font-semibold text-teal-600">全部预警</Link></CardHeader><div className="overflow-x-auto"><table className="data-table"><thead><tr><th>事件</th><th>等级</th><th>风险分</th><th>状态</th><th>时间</th><th/></tr></thead><tbody>{data.latest_alerts.map(item=><tr key={item.id}><td className="font-semibold">{item.title}</td><td><Badge tone={item.risk_level}>{riskLabel(item.risk_level)}</Badge></td><td>{item.risk_score.toFixed(1)}</td><td>{item.status}</td><td>{new Date(item.created_at).toLocaleString('zh-CN')}</td><td><Link href={`/alerts?event=${item.id}`} className="text-teal-600">查看证据</Link></td></tr>)}</tbody></table></div></Card>
</div>}
