'use client'

import { Activity, AlertTriangle, BrainCircuit, CheckCircle2, CircleDot, Database, FileCheck2, LoaderCircle, ShieldCheck, SlidersHorizontal, WalletCards, Workflow } from 'lucide-react'
import type { AgentResponse, ConversationToolCall } from '@/lib/types'
import { Badge } from '@/components/ui/badge'
import { money } from '@/lib/utils'

type AnalysisPanelProps = { response: AgentResponse | null; historicalCalls: ConversationToolCall[]; pending: boolean; customerName?: string }

const fieldLabels: Record<string, string> = {
  amount: '订单金额', currency: '币种', deposit_ratio: '定金比例', credit_days: '账期', identity_verified: '身份核验',
  contract_signed: '正式合同', payer_matches_contract: '付款主体一致', payment_account_changed: '付款账户变化',
  final_payment_due_type: '尾款节点', partial_payment: '分批付款', partial_shipment: '分批发货',
}

function displayValue(key: string, value: unknown) {
  if (value === true) return '是'
  if (value === false) return '否'
  if (key === 'deposit_ratio' && typeof value === 'number') return `${(value * 100).toFixed(0)}%`
  if (key === 'credit_days') return `${String(value)} 天`
  if (key === 'amount' && typeof value === 'number') return value.toLocaleString('zh-CN')
  return String(value)
}

function Section({ icon: Icon, eyebrow, title, children }: { icon: typeof Database; eyebrow: string; title: string; children: React.ReactNode }) {
  return <section className="border-b border-slate-200 px-4 py-4 last:border-b-0"><div className="mb-3 flex items-center gap-2"><span className="grid size-7 place-items-center border border-slate-200 bg-slate-50 text-teal-700"><Icon size={14} /></span><div><p className="text-[8px] font-bold tracking-[.14em] text-slate-400">{eyebrow}</p><h3 className="text-[11px] font-bold text-slate-800">{title}</h3></div></div>{children}</section>
}

export function AgentAnalysisPanel({ response, historicalCalls, pending, customerName }: AnalysisPanelProps) {
  const decision = response?.decision_result
  const context = response?.transaction_context || {}
  const known = Object.entries(context).filter(([key, value]) => fieldLabels[key] && value !== null && value !== undefined)
  const displayedCalls = response?.tools_called.length ? response.tools_called.map((item) => ({ ...item, success: true, error_code: null })) : historicalCalls
  const rules = decision?.transaction_risk.triggered_rules || []
  const comparison = response?.comparison
  return <aside className="flex min-h-0 flex-col overflow-hidden border border-slate-200 bg-white shadow-[0_3px_18px_rgba(15,23,42,.04)]">
    <div className="border-b border-slate-200 bg-[#0c302f] px-4 py-4 text-white"><div className="flex items-center justify-between"><div className="flex items-center gap-2"><Workflow size={17} className="text-teal-300" /><div><p className="text-[8px] font-bold tracking-[.16em] text-teal-200/60">DECISION TRACE</p><h2 className="text-xs font-bold">交易决策证据</h2></div></div><span className={`size-2 rounded-full ${pending ? 'animate-pulse bg-amber-300' : response ? 'bg-emerald-400' : 'bg-slate-500'}`} /></div><p className="mt-2 text-[9px] leading-4 text-teal-100/60">{pending ? 'AI 正在调用确定性风控系统' : response ? `Context v${response.context_version} · ${response.information_completeness.toFixed(0)}% 完整` : '等待交易条件进入决策链'}</p></div>
    <div className="min-h-0 flex-1 overflow-y-auto">
      <Section icon={Activity} eyebrow="01 · TOOL EXECUTION" title="受控工具调用">{pending ? <div className="space-y-2 border-l-2 border-teal-500 pl-3">{['抽取交易条件', '检查关键缺失', '调用确定性决策服务'].map((item, index) => <div key={item} className="flex items-center gap-2 text-[10px] text-slate-600">{index === 1 ? <LoaderCircle size={12} className="animate-spin text-teal-600" /> : <CircleDot size={12} className="text-slate-300" />}{item}</div>)}</div> : displayedCalls.length ? <div className="space-y-2">{displayedCalls.map((call, index) => <div key={`${call.tool}-${index}`} className="border border-slate-200 bg-slate-50/60 px-3 py-2.5"><div className="flex gap-2">{call.success === false ? <AlertTriangle size={13} className="mt-0.5 text-red-500" /> : <CheckCircle2 size={13} className="mt-0.5 text-emerald-600" />}<div><code className="break-all text-[9px] font-bold">{call.tool}</code><p className="mt-1 text-[8px] leading-4 text-slate-400">{call.summary}</p></div></div></div>)}</div> : <p className="text-[10px] text-slate-400">尚未调用业务工具；如果信息不足，Agent 会先主动追问。</p>}</Section>
      <Section icon={Database} eyebrow="02 · DECISION CONTEXT" title="当前交易 Context"><div className="mb-3 flex items-center justify-between text-[9px]"><span className="text-slate-400">客户</span><strong>{response?.related_customer?.company_name || customerName || '首次合作 / 未建档'}</strong></div>{known.length ? <div className="grid grid-cols-2 gap-px overflow-hidden border border-slate-200 bg-slate-200">{known.map(([key, value]) => <div key={key} className="bg-white p-2.5"><span className="block text-[8px] text-slate-400">{fieldLabels[key]}</span><strong className="mt-1 block text-[10px]">{displayValue(key, value)}</strong></div>)}</div> : <p className="text-[10px] text-slate-400">尚未形成结构化交易上下文。</p>}{response?.missing_fields.length ? <div className="mt-3 rounded-lg bg-amber-50 p-3"><p className="text-[8px] font-bold text-amber-800">关键缺失字段</p><div className="mt-2 flex flex-wrap gap-1">{response.missing_fields.map((item) => <Badge key={item} tone="medium" className="text-[7px]">{fieldLabels[item] || item}</Badge>)}</div><p className="mt-2 text-[9px] leading-4 text-amber-800">下一问：{response.next_best_question}</p></div> : response && <p className="mt-3 flex items-center gap-2 text-[9px] text-emerald-700"><CheckCircle2 size={12} />核心决策字段已补齐</p>}</Section>
      {decision && <>
        <Section icon={ShieldCheck} eyebrow="03 · CUSTOMER & TERMS" title="客户可信度与授信条件"><div className="grid grid-cols-2 gap-2">{[
          ['客户可信度', decision.customer_trust.trust_level], ['数据置信度', decision.customer_trust.confidence_level],
          ['建议账期', `${decision.credit_terms.recommended_credit_days} 天`], ['最低定金', `${(decision.credit_terms.recommended_min_deposit_ratio * 100).toFixed(0)}%`],
        ].map(([label, value]) => <div key={label} className="rounded-lg bg-slate-50 p-2.5"><span className="text-[8px] text-slate-400">{label}</span><strong className="mt-1 block text-[11px]">{value}</strong></div>)}</div><Badge tone={decision.decision_status === 'RECOMMENDED' ? 'success' : 'medium'} className="mt-3 text-[8px]">{decision.decision_status}</Badge></Section>
        <Section icon={WalletCards} eyebrow="04 · RISK EXPOSURE" title="风险敞口"><div className="grid grid-cols-2 gap-px overflow-hidden border border-slate-200 bg-slate-200">{[
          ['当前敞口', money(decision.risk_exposure.current_exposure, decision.risk_exposure.currency)],
          ['预计最大敞口', money(decision.risk_exposure.projected_max_exposure, decision.risk_exposure.currency)],
          ['已核验保障', money(decision.risk_exposure.coverage_amount, decision.risk_exposure.currency)],
          ['保障覆盖率', `${(decision.risk_exposure.coverage_ratio * 100).toFixed(0)}%`],
        ].map(([label, value]) => <div key={label} className="bg-white p-2.5"><span className="text-[8px] text-slate-400">{label}</span><strong className="mt-1 block font-mono text-[11px]">{value}</strong></div>)}</div>{comparison && <div className="mt-3 rounded-lg bg-teal-50 p-3 text-[9px] text-teal-800">调整前 → 调整后：敞口变化 {money(comparison.projected_exposure_change, decision.risk_exposure.currency)}，状态 {comparison.decision_status_before} → {comparison.decision_status_after}</div>}</Section>
        <Section icon={FileCheck2} eyebrow="05 · EVIDENCE" title="证据完整度"><div className="flex items-center justify-between"><strong className="text-2xl text-teal-700">{(decision.evidence.completeness * 100).toFixed(0)}%</strong><span className="text-[9px] text-slate-400">关键缺失 {decision.evidence.critical_missing.length}</span></div><div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full bg-teal-500" style={{ width: `${decision.evidence.completeness * 100}%` }} /></div><div className="mt-3 flex flex-wrap gap-1">{decision.evidence.missing.map((item) => <Badge key={item} tone={decision.evidence.critical_missing.includes(item) ? 'critical' : 'medium'} className="text-[7px]">{item}</Badge>)}</div></Section>
        <Section icon={SlidersHorizontal} eyebrow="06 · RULES & MITIGATION" title="规则与缓释">{rules.length ? <div className="space-y-2">{rules.slice(0, 6).map((rule) => <div key={rule.rule_code} className="border-l-2 border-orange-500 bg-orange-50/60 px-3 py-2"><div className="flex justify-between gap-2"><code className="text-[8px] font-bold text-orange-800">{rule.rule_code}</code><span className="text-[7px] text-orange-700">贡献 {rule.risk_contribution ?? '—'}</span></div><p className="mt-1 text-[8px] leading-4 text-orange-900/70">{rule.reason}</p></div>)}</div> : <p className="text-[10px] text-slate-400">未触发确定性规则。</p>}<p className="mt-3 text-[9px] text-slate-500">已核验缓释 {decision.mitigations.verified_mitigations.length} 项；未核验 {decision.mitigations.unverified_mitigations.length} 项。</p></Section>
        <Section icon={BrainCircuit} eyebrow="07 · AUXILIARY SIGNAL" title="辅助异常信号"><div className="rounded-lg bg-slate-950 p-3 text-white"><div className="flex items-center justify-between"><span className="text-[9px]">Behavior Anomaly</span><strong className="font-mono text-teal-300">{(decision.anomaly_signal.anomaly_score * 100).toFixed(0)}%</strong></div><p className="mt-2 text-[8px] leading-4 text-slate-400">{decision.anomaly_signal.explanation}</p></div><p className="mt-2 text-[8px] text-slate-400">该信号不单独决定 HIGH / CRITICAL，也不用于认定欺诈。</p></Section>
      </>}
      {response?.evidence.length ? <Section icon={ShieldCheck} eyebrow="08 · SOURCE REFERENCES" title="证据来源">{response.evidence.slice(0, 6).map((item) => <div key={`${item.source_type}-${item.source_id}`} className="mb-2 text-[8px] leading-4 text-slate-500"><code className="text-teal-700">{item.source_type}#{item.source_id}</code> {item.summary}</div>)}</Section> : null}
    </div>
  </aside>
}
