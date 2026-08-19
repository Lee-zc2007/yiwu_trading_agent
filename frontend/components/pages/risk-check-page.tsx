'use client'

import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowDownRight, ArrowRight, CheckCircle2, FileCheck2, FlaskConical, ShieldAlert, SlidersHorizontal } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import type { Customer, DecisionResult, DecisionSimulation, Paginated, TransactionContext } from '@/lib/types'
import { PageHeader } from '@/components/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input, Select } from '@/components/ui/input'
import { money } from '@/lib/utils'

type FormState = Record<string, string | boolean>

const initial: FormState = {
  customer_id: '', amount: '30000', currency: 'USD', deposit_percent: '20', confirmed_payment_amount: '0',
  final_payment_percent: '80', final_payment_due_type: 'AFTER_DELIVERY', credit_days: '45',
  payer_name: '', contract_entity: '', payer_matches_contract: false, payment_account_changed: false,
  payment_account_verified: false, contract_signed: false, identity_verified: false,
  insurance_coverage: '0', insurance_verified: false, guarantee_coverage: '0', guarantee_verified: false,
  lc_coverage: '0', lc_verified: false, platform_coverage: '0', platform_verified: false,
  partial_payment: true, partial_shipment: true, product_category: '家居用品',
}

const evidenceLabels: Record<string, string> = {
  IDENTITY: '企业身份', CONTRACT: '正式合同', PAYER_IDENTITY: '付款主体', PAYMENT_TERMS: '付款条款',
  INSPECTION: '验货记录', SHIPPING: '发货凭证', INSURANCE_POLICY: '保险保单', LETTER_OF_CREDIT: '信用证',
  PLATFORM_GUARANTEE: '平台保障',
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (value: boolean) => void; label: string }) {
  return <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-[10px] font-semibold text-slate-600"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="size-4 accent-teal-600" />{label}</label>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label><span className="mb-1.5 block text-[10px] font-semibold text-slate-500">{label}</span>{children}</label>
}

function DecisionCards({ result }: { result: DecisionResult }) {
  const risk = result.transaction_risk
  const exposure = result.risk_exposure
  return <div className="space-y-4">
    <Card className="overflow-hidden"><div className="grid gap-px bg-slate-200 sm:grid-cols-4">
      {[
        ['客户可信度', result.customer_trust.trust_level, result.customer_trust.confidence_level],
        ['本次交易风险', risk.risk_level, `${risk.triggered_rules.length} 条规则`],
        ['预计最大敞口', money(exposure.projected_max_exposure, exposure.currency), `当前 ${money(exposure.current_exposure, exposure.currency)}`],
        ['证据完整度', `${(result.evidence.completeness * 100).toFixed(0)}%`, `${result.evidence.critical_missing.length} 项关键缺失`],
      ].map(([label, value, caption]) => <div key={label} className="bg-white p-4"><span className="text-[9px] font-semibold text-slate-400">{label}</span><strong className="mt-2 block text-lg text-slate-800">{value}</strong><small className="text-[8px] text-slate-400">{caption}</small></div>)}
    </div></Card>
    <div className="grid gap-4 xl:grid-cols-2">
      <Card><CardHeader><h3 className="text-sm font-bold">规则触发与数字证据</h3><Badge tone={risk.risk_level}>{risk.risk_level}</Badge></CardHeader><div className="divide-y divide-slate-100">{risk.triggered_rules.length ? risk.triggered_rules.map((rule) => <div key={rule.rule_code} className="p-4"><div className="flex items-center justify-between gap-2"><code className="text-[10px] font-bold text-orange-700">{rule.rule_code}</code><span className="text-[9px] text-slate-400">贡献 {rule.risk_contribution ?? '—'}</span></div><p className="mt-2 text-xs text-slate-700">{rule.reason}</p><pre className="mt-2 overflow-auto rounded-lg bg-slate-950 p-3 text-[8px] leading-4 text-teal-200">{JSON.stringify(rule.evidence, null, 2)}</pre></div>) : <p className="p-5 text-xs text-slate-400">未触发确定性风险规则。</p>}</div></Card>
      <div className="space-y-4">
        <Card><CardHeader><h3 className="text-sm font-bold">证据与缓释</h3><FileCheck2 size={17} className="text-teal-600" /></CardHeader><CardContent><div className="flex flex-wrap gap-2">{result.evidence.required.map((item) => <Badge key={item.evidence_type} tone={result.evidence.verified.includes(item.evidence_type) ? 'success' : item.critical ? 'critical' : 'medium'}>{evidenceLabels[item.evidence_type] || item.evidence_type}</Badge>)}</div><p className="mt-4 text-[10px] leading-5 text-slate-500">已核验保障 {money(result.mitigations.coverage_amount, result.mitigations.currency)}，覆盖率 {(result.mitigations.coverage_ratio * 100).toFixed(0)}%。未核验保障不会抵扣敞口。</p></CardContent></Card>
        <Card><CardHeader><h3 className="text-sm font-bold">建议交易条件</h3><Badge tone={result.decision_status === 'RECOMMENDED' ? 'success' : 'medium'}>{result.decision_status}</Badge></CardHeader><CardContent className="space-y-2">{[
          `建议最低定金 ${(result.credit_terms.recommended_min_deposit_ratio * 100).toFixed(0)}%`,
          `建议账期不超过 ${result.credit_terms.recommended_credit_days} 天`,
          `建议最大未保障敞口 ${money(result.credit_terms.recommended_max_exposure, exposure.currency)}`,
          ...result.recommendations,
        ].map((item) => <p key={item} className="flex gap-2 text-xs leading-5"><CheckCircle2 size={14} className="mt-0.5 shrink-0 text-teal-600" />{item}</p>)}<p className="mt-3 rounded-lg bg-amber-50 p-3 text-[10px] leading-5 text-amber-800">{result.disclaimer}</p></CardContent></Card>
        <Card><CardHeader><h3 className="text-sm font-bold">辅助异常信号</h3><Badge tone="neutral">不单独定级</Badge></CardHeader><CardContent><p className="text-xs text-slate-600">{result.anomaly_signal.explanation}</p><p className="mt-2 font-mono text-[9px] text-slate-400">{result.anomaly_signal.model_version} · {(result.anomaly_signal.anomaly_score * 100).toFixed(0)}%</p></CardContent></Card>
      </div>
    </div>
  </div>
}

export function RiskCheckPage() {
  const [form, setForm] = useState<FormState>(initial)
  const [result, setResult] = useState<DecisionResult | null>(null)
  const [simulation, setSimulation] = useState<DecisionSimulation | null>(null)
  const customers = useQuery({ queryKey: ['decision-customers'], queryFn: () => api<Paginated<Customer>>('/api/customers?page_size=100') })
  const set = (key: string, value: string | boolean) => setForm((current) => ({ ...current, [key]: value }))
  const context = useMemo<TransactionContext>(() => {
    const amount = Number(form.amount)
    const mitigations = [
      ['INSURANCE', form.insurance_coverage, form.insurance_verified], ['GUARANTEE', form.guarantee_coverage, form.guarantee_verified],
      ['LETTER_OF_CREDIT', form.lc_coverage, form.lc_verified], ['PLATFORM_PROTECTION', form.platform_coverage, form.platform_verified],
    ].filter(([, coverage]) => Number(coverage) > 0).map(([mitigation_type, coverage_amount, verified]) => ({ mitigation_type, coverage_amount: Number(coverage_amount), verified: Boolean(verified), currency: String(form.currency) }))
    return {
      amount, currency: String(form.currency), deposit_ratio: Number(form.deposit_percent) / 100,
      confirmed_payment_amount: Number(form.confirmed_payment_amount), final_payment_ratio: Number(form.final_payment_percent) / 100,
      final_payment_due_type: String(form.final_payment_due_type), credit_days: Number(form.credit_days),
      payer_name: form.payer_name, contract_entity: form.contract_entity, payer_matches_contract: Boolean(form.payer_matches_contract),
      payment_account_changed: Boolean(form.payment_account_changed), payment_account_verified: Boolean(form.payment_account_verified),
      contract_signed: Boolean(form.contract_signed), identity_verified: Boolean(form.identity_verified),
      partial_payment: Boolean(form.partial_payment), partial_shipment: Boolean(form.partial_shipment),
      planned_shipping_value: amount, planned_payment_before_shipping: amount * Number(form.deposit_percent) / 100,
      product_category: String(form.product_category), payment_terms_verified: Boolean(form.contract_signed), mitigations,
    }
  }, [form])
  const evaluate = useMutation({ mutationFn: () => api<DecisionResult>('/api/decisions/evaluate', { method: 'POST', body: JSON.stringify({ customer_id: form.customer_id ? Number(form.customer_id) : null, transaction_context: context }) }), onSuccess: (data) => { setResult(data); setSimulation(null); toast.success('交易授信决策已完成') }, onError: (error: Error) => toast.error(error.message) })
  const simulate = useMutation({ mutationFn: (adjustments: Record<string, unknown>) => api<DecisionSimulation>('/api/decisions/simulate', { method: 'POST', body: JSON.stringify({ customer_id: form.customer_id ? Number(form.customer_id) : null, base_context: context, adjustments }) }), onSuccess: (data) => { setSimulation(data); toast.success('调整方案已模拟，正式交易未修改') }, onError: (error: Error) => toast.error(error.message) })
  return <div><PageHeader eyebrow="TRANSACTION CREDIT DECISION" title="交易授信决策" description="围绕客户历史、本次交易条件、风险敞口、关键证据与缓释保障形成可执行建议；系统不自动批准或拒绝交易。" />
    <div className="grid gap-4 xl:grid-cols-[430px_minmax(0,1fr)]">
      <Card><CardHeader><div><h2 className="text-sm font-bold">拟议交易条件</h2><p className="mt-1 text-[9px] text-slate-400">金额必须明确币种，保障仅在核验后抵扣</p></div><SlidersHorizontal size={17} className="text-teal-600" /></CardHeader><CardContent className="space-y-5">
        <section><h3 className="mb-3 text-[10px] font-bold tracking-[.12em] text-slate-400">订单与付款</h3><div className="grid grid-cols-2 gap-3"><Field label="关联外商（可选）"><Select value={String(form.customer_id)} onChange={(e) => set('customer_id', e.target.value)}><option value="">首次合作 / 未建档</option>{customers.data?.items.map((customer) => <option key={customer.id} value={customer.id}>#{customer.id} {customer.company_name}</option>)}</Select></Field><Field label="商品品类"><Input value={String(form.product_category)} onChange={(e) => set('product_category', e.target.value)} /></Field><Field label="订单金额"><Input type="number" value={String(form.amount)} onChange={(e) => set('amount', e.target.value)} /></Field><Field label="币种"><Select value={String(form.currency)} onChange={(e) => set('currency', e.target.value)}>{['USD', 'CNY', 'EUR'].map((item) => <option key={item}>{item}</option>)}</Select></Field><Field label="定金比例 %"><Input type="number" min="0" max="100" value={String(form.deposit_percent)} onChange={(e) => set('deposit_percent', e.target.value)} /></Field><Field label="已确认收款"><Input type="number" min="0" value={String(form.confirmed_payment_amount)} onChange={(e) => set('confirmed_payment_amount', e.target.value)} /></Field><Field label="尾款比例 %"><Input type="number" min="0" max="100" value={String(form.final_payment_percent)} onChange={(e) => set('final_payment_percent', e.target.value)} /></Field><Field label="账期天数"><Input type="number" min="0" value={String(form.credit_days)} onChange={(e) => set('credit_days', e.target.value)} /></Field><Field label="尾款支付节点"><Select value={String(form.final_payment_due_type)} onChange={(e) => set('final_payment_due_type', e.target.value)}><option value="BEFORE_SHIPMENT">发货前</option><option value="AFTER_SHIPMENT">发货后</option><option value="ON_DELIVERY">交付时</option><option value="AFTER_DELIVERY">交付后</option></Select></Field></div></section>
        <section><h3 className="mb-3 text-[10px] font-bold tracking-[.12em] text-slate-400">主体与关键证据</h3><div className="grid grid-cols-2 gap-3"><Field label="付款主体"><Input placeholder="客户付款企业" value={String(form.payer_name)} onChange={(e) => set('payer_name', e.target.value)} /></Field><Field label="合同主体"><Input placeholder="合同签约企业" value={String(form.contract_entity)} onChange={(e) => set('contract_entity', e.target.value)} /></Field>{[
          ['payer_matches_contract', '付款主体一致'], ['payment_account_changed', '付款账户已改变'], ['payment_account_verified', '新付款账户已核验'], ['contract_signed', '正式合同已签署'], ['identity_verified', '企业身份已核验'], ['partial_payment', '采用分批付款'], ['partial_shipment', '采用分批发货'],
        ].map(([key, label]) => <Toggle key={key} label={label} checked={Boolean(form[key])} onChange={(value) => set(key, value)} />)}</div></section>
        <section><h3 className="mb-3 text-[10px] font-bold tracking-[.12em] text-slate-400">风险保障金额</h3><div className="grid grid-cols-2 gap-3">{[
          ['insurance', '保险'], ['guarantee', '担保'], ['lc', '信用证'], ['platform', '平台保障'],
        ].map(([key, label]) => <div key={key} className="rounded-lg border border-slate-200 p-3"><span className="text-[10px] font-semibold">{label}</span><Input className="mt-2" type="number" min="0" value={String(form[`${key}_coverage`])} onChange={(e) => set(`${key}_coverage`, e.target.value)} /><label className="mt-2 flex items-center gap-2 text-[9px] text-slate-500"><input type="checkbox" checked={Boolean(form[`${key}_verified`])} onChange={(e) => set(`${key}_verified`, e.target.checked)} className="accent-teal-600" />已完成核验</label></div>)}</div></section>
        <Button className="w-full" onClick={() => evaluate.mutate()} disabled={evaluate.isPending}>{evaluate.isPending ? '正在汇总确定性证据…' : <>执行交易决策<ArrowRight size={15} /></>}</Button>
      </CardContent></Card>
      <div className="space-y-4">{!result ? <Card className="grid min-h-[620px] place-items-center border-dashed"><div className="max-w-sm text-center"><div className="mx-auto grid size-16 place-items-center rounded-2xl bg-teal-50 text-teal-700"><ShieldAlert size={30} /></div><h3 className="mt-5 font-bold">等待交易条件评估</h3><p className="mt-2 text-xs leading-6 text-slate-400">结果将区分客户历史可信度与本次交易风险，并展示敞口、证据和可调整条件。</p></div></Card> : <><Card><CardHeader><div><h3 className="text-sm font-bold">调整条件模拟</h3><p className="mt-1 text-[9px] text-slate-400">只计算，不修改正式交易</p></div><FlaskConical size={17} className="text-teal-600" /></CardHeader><CardContent className="flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={() => simulate.mutate({ deposit_ratio: 0.4 })}>定金提高到 40%</Button><Button variant="outline" size="sm" onClick={() => simulate.mutate({ credit_days: 30 })}>账期缩短到 30 天</Button><Button variant="outline" size="sm" onClick={() => simulate.mutate({ partial_shipment: true })}>改为分批发货</Button></CardContent>{simulation && <div className="grid gap-px border-t border-slate-200 bg-slate-200 sm:grid-cols-3"><div className="bg-white p-4"><span className="text-[9px] text-slate-400">调整前敞口</span><strong className="mt-1 block">{money(simulation.before.risk_exposure.projected_max_exposure, simulation.before.risk_exposure.currency)}</strong></div><div className="grid place-items-center bg-teal-50 p-4 text-teal-700"><ArrowDownRight size={20} /><strong>{money(simulation.comparison.projected_exposure_change, simulation.after.risk_exposure.currency)}</strong></div><div className="bg-white p-4"><span className="text-[9px] text-slate-400">调整后敞口</span><strong className="mt-1 block">{money(simulation.after.risk_exposure.projected_max_exposure, simulation.after.risk_exposure.currency)}</strong></div></div>}</Card><DecisionCards result={simulation?.after || result} /></> }</div>
    </div>
  </div>
}
