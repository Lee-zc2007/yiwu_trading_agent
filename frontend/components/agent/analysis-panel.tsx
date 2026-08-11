'use client'

import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  CircleDot,
  Database,
  FileSearch,
  LoaderCircle,
  Radar,
  ShieldCheck,
  Workflow,
} from 'lucide-react'
import type { AgentResponse, AgentToolResult, ConversationToolCall } from '@/lib/types'
import { Badge } from '@/components/ui/badge'

type AnalysisPanelProps = {
  response: AgentResponse | null
  historicalCalls: ConversationToolCall[]
  pending: boolean
  customerName?: string
}

type AnyRecord = Record<string, unknown>

function record(value: unknown): AnyRecord | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as AnyRecord : null
}

function numberValue(value: unknown): number | null {
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function toolResult(response: AgentResponse | null, name: string): AgentToolResult | null {
  if (!response) return null
  for (const snapshot of [...response.state_history].reverse()) {
    const result = [...snapshot.tool_results].reverse().find((item) => item.tool === name && item.success)
    if (result) return result
  }
  return null
}

function formatAmount(value: number | null) {
  if (value === null) return '—'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value)
}

function formatScore(value: number | null, digits = 2) {
  return value === null ? '—' : value.toFixed(digits)
}

function Section({
  icon: Icon,
  eyebrow,
  title,
  children,
}: {
  icon: typeof Database
  eyebrow: string
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="border-b border-slate-200 px-4 py-4 last:border-b-0">
      <div className="mb-3 flex items-center gap-2">
        <span className="grid size-7 place-items-center border border-slate-200 bg-slate-50 text-teal-700">
          <Icon size={14} />
        </span>
        <div>
          <p className="text-[8px] font-bold tracking-[.14em] text-slate-400">{eyebrow}</p>
          <h3 className="text-[11px] font-bold text-slate-800">{title}</h3>
        </div>
      </div>
      {children}
    </section>
  )
}

export function AgentAnalysisPanel({ response, historicalCalls, pending, customerName }: AnalysisPanelProps) {
  const risk = record(toolResult(response, 'get_order_risk_analysis')?.data)
  const credit = record(toolResult(response, 'get_customer_credit_score')?.data)
  const transactions = record(toolResult(response, 'get_customer_transactions')?.data)
  const features = record(risk?.feature_snapshot)
  const orderAmount = numberValue(features?.order_amount)
  const amountRatio = numberValue(features?.amount_to_history_mean)
  const historicalMean = orderAmount !== null && amountRatio ? orderAmount / amountRatio : null
  const addressChanges = numberValue(features?.address_change_count_30d)
  const anomalyScore = numberValue(risk?.anomaly_score)
  const statisticalScore = numberValue(risk?.statistical_anomaly_score)
  const creditScore = numberValue(risk?.credit_score) ?? numberValue(credit?.total_score)
  const rules = Array.isArray(risk?.triggered_rules) ? risk.triggered_rules.map(record).filter(Boolean) as AnyRecord[] : []
  const recentTransactions = Array.isArray(transactions?.recent_transactions)
    ? transactions.recent_transactions.map(record).filter(Boolean) as AnyRecord[]
    : []
  const orderNumber = recentTransactions.find((item) => numberValue(item.order_id) === numberValue(risk?.order_id))?.order_number
    ?? recentTransactions[0]?.order_number
  const currentCalls = response?.tools_called ?? []
  const displayedCalls = currentCalls.length
    ? currentCalls.map((item) => ({ ...item, success: true, error_code: null }))
    : historicalCalls

  return (
    <aside className="flex min-h-0 flex-col overflow-hidden border border-slate-200 bg-white shadow-[0_3px_18px_rgba(15,23,42,.04)]">
      <div className="border-b border-slate-200 bg-[#0c302f] px-4 py-4 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Workflow size={17} className="text-teal-300" />
            <div>
              <p className="text-[8px] font-bold tracking-[.16em] text-teal-200/60">AGENT TRACE</p>
              <h2 className="text-xs font-bold">风控分析过程</h2>
            </div>
          </div>
          <span className={`size-2 rounded-full ${pending ? 'animate-pulse bg-amber-300' : response ? 'bg-emerald-400' : 'bg-slate-500'}`} />
        </div>
        <p className="mt-2 text-[9px] leading-4 text-teal-100/60">
          {pending ? 'AI 正在调用风控系统分析' : response ? '本次分析链路已完成并固化证据' : '等待业务问题进入风控工具链'}
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <Section icon={Activity} eyebrow="01 · TOOL EXECUTION" title="调用工具">
          {pending ? (
            <div className="space-y-2 border-l-2 border-teal-500 pl-3">
              {['识别业务意图', '选择只读风控工具', '汇总证据并生成结论'].map((item, index) => (
                <div key={item} className="flex items-center gap-2 text-[10px] text-slate-600">
                  {index === 1 ? <LoaderCircle size={12} className="animate-spin text-teal-600" /> : <CircleDot size={12} className="text-slate-300" />}
                  {item}
                </div>
              ))}
            </div>
          ) : displayedCalls.length ? (
            <div className="space-y-2">
              {displayedCalls.map((call, index) => (
                <div key={`${call.tool}-${index}`} className="border border-slate-200 bg-slate-50/60 px-3 py-2.5">
                  <div className="flex items-start gap-2">
                    {call.success === false
                      ? <AlertTriangle size={13} className="mt-0.5 shrink-0 text-red-500" />
                      : <CheckCircle2 size={13} className="mt-0.5 shrink-0 text-emerald-600" />}
                    <div className="min-w-0">
                      <code className="break-all text-[9px] font-bold text-slate-800">{call.tool}</code>
                      <p className="mt-1 text-[8px] leading-4 text-slate-400">{call.summary}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[10px] leading-5 text-slate-400">尚未发起分析。工具执行后将在这里显示成功状态与调用顺序。</p>
          )}
        </Section>

        <Section icon={Database} eyebrow="02 · DATA SCOPE" title="数据来源">
          <div className="grid grid-cols-[68px_1fr] gap-y-2 text-[10px]">
            <span className="text-slate-400">客户</span>
            <strong className="truncate text-slate-700">
              {response?.related_customer?.company_name || (response?.related_customer?.id ? customerName || `客户 #${response.related_customer.id}` : '—')}
            </strong>
            <span className="text-slate-400">订单</span>
            <strong className="truncate text-slate-700">
              {String(orderNumber || (response?.related_orders[0] ? `订单 #${response.related_orders[0]}` : '—'))}
            </strong>
            <span className="text-slate-400">风险事件</span>
            <strong className="text-slate-700">{response?.risk_events.length ? response.risk_events.map((id) => `#${id}`).join('、') : '—'}</strong>
          </div>
          {!!response?.evidence.length && (
            <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-3">
              {response.evidence.slice(0, 4).map((item) => (
                <div key={`${item.source_type}-${item.source_id}`} className="flex gap-2 text-[8px] leading-4 text-slate-500">
                  <span className="font-mono text-teal-700">{item.source_type}#{item.source_id}</span>
                  <span className="line-clamp-2">{item.summary}</span>
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section icon={FileSearch} eyebrow="03 · RISK EVIDENCE" title="风险证据">
          <div className="grid grid-cols-2 gap-px overflow-hidden border border-slate-200 bg-slate-200">
            {[
              ['订单金额', formatAmount(orderAmount), 'USD'],
              ['历史均值', formatAmount(historicalMean), 'USD'],
              ['异常倍数', amountRatio === null ? '—' : `${amountRatio.toFixed(1)}×`, '金额偏离'],
              ['地址变化', formatScore(addressChanges, 0), '近 30 天'],
              ['信用评分', formatScore(creditScore, 1), '已保存评分'],
              ['综合风险', formatScore(numberValue(risk?.overall_risk_score), 1), String(risk?.risk_level || '等级未生成')],
            ].map(([label, value, caption]) => (
              <div key={label} className="bg-white p-2.5">
                <span className="block text-[8px] text-slate-400">{label}</span>
                <strong className="mt-1 block font-mono text-[14px] text-slate-800">{value}</strong>
                <small className="text-[7px] text-slate-400">{caption}</small>
              </div>
            ))}
          </div>
        </Section>

        <Section icon={ShieldCheck} eyebrow="04 · RULE ENGINE" title="触发规则">
          {rules.length ? (
            <div className="space-y-2">
              {rules.map((rule) => (
                <div key={String(rule.rule_code)} className="border-l-2 border-orange-500 bg-orange-50/60 px-3 py-2">
                  <div className="flex items-center justify-between gap-2">
                    <code className="text-[9px] font-bold text-orange-800">{String(rule.rule_code)}</code>
                    <Badge tone={String(rule.risk_level)} className="px-1.5 py-0.5 text-[8px]">{String(rule.risk_score)} 分</Badge>
                  </div>
                  <p className="mt-1 text-[8px] leading-4 text-orange-900/65">{String(rule.reason)}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[10px] text-slate-400">当前回答未返回规则命中结果。</p>
          )}
        </Section>

        <Section icon={BrainCircuit} eyebrow="05 · MODEL OUTPUT" title="模型结果">
          <div className="border border-slate-200 bg-slate-950 p-3 text-white">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Radar size={15} className="text-teal-300" />
                <span className="text-[10px] font-bold">Isolation Forest</span>
              </div>
              <strong className="font-mono text-lg text-teal-300">{formatScore(anomalyScore, 2)}</strong>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden bg-white/10">
              <div className="h-full bg-teal-400" style={{ width: `${Math.max(0, Math.min(100, (anomalyScore ?? 0) * 100))}%` }} />
            </div>
            <div className="mt-2 flex justify-between text-[7px] text-slate-400">
              <span>{String(risk?.model_version || '等待模型输出')}</span>
              <span>统计异常 {formatScore(statisticalScore, 2)}</span>
            </div>
          </div>
          {response && <p className="mt-3 text-[8px] leading-4 text-slate-400">{response.disclaimer}</p>}
        </Section>
      </div>
    </aside>
  )
}
