'use client'

import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, BadgeCheck, CalendarDays, CircleDollarSign, FileWarning, History, RefreshCw, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import type { CreditScore, Customer, CustomerTrust, Paginated, RiskEvent, Transaction } from '@/lib/types'
import { money } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Badge, riskLabel } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Chart } from '@/components/chart'
import { ErrorState, Loading } from '@/components/states'
import { ScoreRing } from '@/components/score-ring'

function Metric({ label, value, caption }: { label: string; value: string; caption?: string }) {
  return <div className="rounded-lg border border-slate-200 bg-white p-3"><span className="text-[9px] font-semibold text-slate-400">{label}</span><strong className="mt-1.5 block text-lg text-slate-800">{value}</strong>{caption && <small className="text-[8px] text-slate-400">{caption}</small>}</div>
}

const rate = (value: number | null) => value === null ? '未知' : `${(value * 100).toFixed(0)}%`

export function CustomerDetailPage({ id }: { id: number }) {
  const queryClient = useQueryClient()
  const profile = useQuery({ queryKey: ['customer', id], queryFn: () => api<Customer>(`/api/customers/${id}`) })
  const trust = useQuery({ queryKey: ['customer-trust', id], queryFn: () => api<CustomerTrust>(`/api/customers/${id}/trust`) })
  const score = useQuery({ queryKey: ['credit', id], queryFn: () => api<CreditScore>(`/api/customers/${id}/credit-score`) })
  const history = useQuery({ queryKey: ['credit-history', id], queryFn: () => api<CreditScore[]>(`/api/customers/${id}/credit-score/history`) })
  const transactions = useQuery({ queryKey: ['customer-transactions', id], queryFn: () => api<Paginated<Transaction>>(`/api/transactions?customer_id=${id}&page_size=50`) })
  const alerts = useQuery({ queryKey: ['customer-alerts', id], queryFn: () => api<Paginated<RiskEvent>>('/api/risk/alerts?page_size=100') })
  const recalculate = useMutation({ mutationFn: () => api<CreditScore>(`/api/customers/${id}/credit-score/recalculate`, { method: 'POST' }), onSuccess: () => { toast.success('Legacy 信用评分已重算'); queryClient.invalidateQueries({ queryKey: ['credit', id] }); queryClient.invalidateQueries({ queryKey: ['credit-history', id] }); queryClient.invalidateQueries({ queryKey: ['customer-trust', id] }) }, onError: (error: Error) => toast.error(error.message) })
  if (profile.isLoading || trust.isLoading || score.isLoading) return <Loading />
  if (profile.error || trust.error || score.error) return <ErrorState message={(profile.error || trust.error || score.error)?.message || '加载失败'} />
  const customer = profile.data!
  const customerTrust = trust.data!
  const legacyScore = score.data!
  const rows = transactions.data?.items || []
  const customerAlerts = (alerts.data?.items || []).filter((item) => item.customer_id === id)
  const amountOption = { tooltip: { trigger: 'axis' }, grid: { left: 50, right: 10, top: 15, bottom: 35 }, xAxis: { type: 'category', data: [...rows].reverse().map((item) => item.order_number.slice(-3)), axisLabel: { fontSize: 9 } }, yAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf2f2' } } }, series: [{ type: 'bar', data: [...rows].reverse().map((item) => item.amount), itemStyle: { color: '#2a9d8f', borderRadius: [4, 4, 0, 0] } }] }
  const scoreOption = { tooltip: { trigger: 'axis' }, grid: { left: 35, right: 10, top: 15, bottom: 25 }, xAxis: { type: 'category', data: (history.data || []).map((item) => new Date(item.calculated_at).toLocaleDateString('zh-CN')) }, yAxis: { type: 'value', min: 0, max: 100, splitLine: { lineStyle: { color: '#edf2f2' } } }, series: [{ type: 'line', smooth: true, data: (history.data || []).map((item) => item.total_score), lineStyle: { color: '#64748b', width: 2 }, itemStyle: { color: '#64748b' } }] }
  return <div>
    <div className="mb-5 flex items-center justify-between"><Link href="/customers" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-teal-600"><ArrowLeft size={15} />返回外商列表</Link><Button variant="outline" onClick={() => recalculate.mutate()} disabled={recalculate.isPending}><RefreshCw size={15} className={recalculate.isPending ? 'animate-spin' : ''} />重算 Legacy 信用分</Button></div>
    <Card className="overflow-hidden"><div className="h-24 bg-gradient-to-r from-[#0b3532] via-[#115e59] to-[#21877e]" /><div className="flex flex-col gap-5 px-6 pb-6 sm:flex-row sm:items-end"><div className="-mt-10 grid size-20 place-items-center rounded-2xl border-4 border-white bg-teal-100 text-2xl font-bold text-teal-700">{customer.company_name.slice(0, 1)}</div><div className="flex-1 sm:pb-1"><div className="flex flex-wrap items-center gap-2"><h1 className="text-xl font-bold">{customer.company_name}</h1>{customer.identity_verified && <Badge tone="success"><BadgeCheck size={12} />身份已验证</Badge>}{customer.watchlist_status && <Badge tone="medium">观察名单</Badge>}</div><p className="mt-1 text-xs text-slate-500">{customer.name} · {customer.country} · {customer.industry}</p></div><div className="text-right"><Badge tone={customerTrust.trust_level === 'high' ? 'success' : customerTrust.trust_level === 'low' ? 'high' : 'medium'}>{customerTrust.trust_level}</Badge><p className="mt-2 text-[9px] text-slate-400">Customer Trust v2 · {customerTrust.confidence_level}</p></div></div></Card>
    <Card className="mt-4"><CardHeader><div><h2 className="text-sm font-bold">客户历史可信度</h2><p className="mt-1 text-[10px] text-slate-400">回答“这个客户过去是否可靠”，不混入本次订单金额异常</p></div><ShieldCheck size={18} className="text-teal-600" /></CardHeader><CardContent><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><Metric label="合作年限" value={`${(customerTrust.cooperation_days / 365).toFixed(1)} 年`} caption={`${customerTrust.cooperation_days} 天`} /><Metric label="合作次数" value={`${customerTrust.transaction_count} 笔`} caption={customerTrust.confidence_level} /><Metric label="累计交易额" value={money(customerTrust.total_amount)} /><Metric label="历史最大订单" value={money(customerTrust.max_order_amount)} /><Metric label="准时付款率" value={rate(customerTrust.on_time_payment_rate)} caption={customerTrust.on_time_payment_rate === null ? '缺少明确到期日，不强行判定' : `${customerTrust.payment_timing_assessed_count} 笔可核验`} /><Metric label="延期次数" value={`${customerTrust.overdue_count} 次`} caption={`平均 ${customerTrust.average_overdue_days ?? '未知'} 天`} /><Metric label="历史纠纷" value={`${customerTrust.dispute_count} 笔`} caption={rate(customerTrust.dispute_rate)} /><Metric label="历史退款" value={`${customerTrust.refund_count} 笔`} caption={rate(customerTrust.refund_rate)} /><Metric label="历史拒收/取消" value={`${customerTrust.rejection_count} 笔`} /><Metric label="数据缺口" value={`${customerTrust.missing_fields.length} 项`} caption={customerTrust.missing_fields.join('、') || '关键历史字段完整'} /></div></CardContent></Card>
    <div className="mt-4 grid gap-4 xl:grid-cols-[1.3fr_.7fr]"><Card><CardHeader><div><h3 className="text-sm font-bold">订单金额与历史账期</h3><p className="mt-1 text-[10px] text-slate-400">金额异常属于 Transaction Risk，不直接降低客户历史可信度</p></div><CircleDollarSign size={17} className="text-teal-600" /></CardHeader><CardContent><Chart option={amountOption} className="h-64" /></CardContent></Card><Card><CardHeader><div><h3 className="text-sm font-bold">Legacy 信用评分</h3><p className="mt-1 text-[10px] text-slate-400">仅作兼容参考，不是页面视觉中心</p></div><History size={17} className="text-slate-400" /></CardHeader><CardContent><div className="flex items-center gap-5"><ScoreRing score={legacyScore.total_score} size="sm" /><div><strong className="text-sm">{legacyScore.risk_level}</strong><p className="mt-1 text-[9px] text-slate-400">{legacyScore.confidence_level} · {legacyScore.rule_version}</p></div></div><Chart option={scoreOption} className="mt-4 h-36" /></CardContent></Card></div>
    <div className="mt-4 grid gap-4 xl:grid-cols-[1.3fr_.7fr]"><Card><CardHeader><h3 className="text-sm font-bold">历史订单 · {rows.length}</h3><CalendarDays size={17} className="text-teal-600" /></CardHeader><div className="overflow-x-auto"><table className="data-table"><thead><tr><th>订单号</th><th>品类</th><th>金额</th><th>付款方式</th><th>履约</th></tr></thead><tbody>{rows.slice(0, 10).map((transaction) => <tr key={transaction.id}><td className="font-semibold">{transaction.order_number}</td><td>{transaction.product_category}</td><td>{money(transaction.amount, transaction.currency)}</td><td>{transaction.payment_method}</td><td><Badge tone={transaction.overdue_days || transaction.dispute_status !== 'none' ? 'high' : 'success'}>{transaction.overdue_days ? `逾期${transaction.overdue_days}天` : '正常'}</Badge></td></tr>)}</tbody></table></div></Card><Card><CardHeader><h3 className="text-sm font-bold">关联风险事件 · {customerAlerts.length}</h3><FileWarning size={17} className="text-orange-500" /></CardHeader><div className="divide-y divide-slate-100">{customerAlerts.slice(0, 8).map((event) => <Link href={`/alerts?event=${event.id}`} key={event.id} className="block p-4 hover:bg-slate-50"><div className="flex items-center justify-between"><Badge tone={event.risk_level}>{riskLabel(event.risk_level)}</Badge><strong className="text-sm">{event.risk_score.toFixed(0)}</strong></div><p className="mt-2 text-xs font-semibold">{event.title}</p><p className="mt-1 line-clamp-2 text-[9px] text-slate-400">{event.description}</p></Link>)}</div></Card></div>
  </div>
}
