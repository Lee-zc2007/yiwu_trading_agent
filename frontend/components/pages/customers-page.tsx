'use client'

import Link from 'next/link'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ChevronLeft, ChevronRight, Plus, Search, ShieldQuestion, X } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import type { Customer, Paginated } from '@/lib/types'
import { PageHeader } from '@/components/page-header'
import { Card } from '@/components/ui/card'
import { Input, Select, Textarea } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { ErrorState, Loading } from '@/components/states'
import { ScoreRing } from '@/components/score-ring'
import { Button } from '@/components/ui/button'

const initialCustomer = {
  name: '', company_name: '', country: '', region: '', registration_number: '', email: '', phone: '',
  industry: 'Retail & Wholesale', main_product_category: '家居用品', identity_verified: false,
  blacklist_status: false, watchlist_status: false, cooperation_start_date: new Date().toISOString().slice(0, 10), notes: '',
}

export function CustomersPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [country, setCountry] = useState('')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState(initialCustomer)
  const query = useQuery({
    queryKey: ['customers', search, country, page],
    queryFn: () => api<Paginated<Customer>>(`/api/customers?search=${encodeURIComponent(search)}&country=${encodeURIComponent(country)}&page=${page}&page_size=12`),
  })
  const create = useMutation({
    mutationFn: () => api<Customer>('/api/customers', { method: 'POST', body: JSON.stringify(form) }),
    onSuccess: () => {
      toast.success('外商档案已创建并完成初始评分')
      setOpen(false)
      setForm(initialCustomer)
      qc.invalidateQueries({ queryKey: ['customers'] })
    },
    onError: error => toast.error(error.message),
  })

  return <div>
    <PageHeader eyebrow="CUSTOMER INTELLIGENCE" title="外商档案" description="统一查看身份资料、合作历史、信用等级和风险状态；所有查询按 Merchant ID 隔离。" actions={<Button onClick={() => setOpen(true)}><Plus size={15}/>新增外商</Button>}/>
    <Card className="mb-4 flex flex-col gap-3 p-4 sm:flex-row">
      <div className="relative flex-1"><Search className="absolute left-3 top-3 text-slate-400" size={15}/><Input className="pl-9" placeholder="搜索姓名或企业名称" value={search} onChange={event => { setSearch(event.target.value); setPage(1) }}/></div>
      <Select className="sm:w-48" value={country} onChange={event => { setCountry(event.target.value); setPage(1) }}><option value="">全部国家</option>{['France', 'United States', 'UAE', 'Germany', 'Japan', 'Saudi Arabia'].map(item => <option key={item}>{item}</option>)}</Select>
    </Card>
    {query.isLoading ? <Loading/> : query.error ? <ErrorState message={query.error.message}/> : <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{query.data?.items.map(customer => <Link href={`/customers/${customer.id}`} key={customer.id}><Card className="group flex h-full items-center gap-4 p-4 hover:-translate-y-0.5 hover:border-teal-300 hover:shadow-lg"><ScoreRing score={customer.current_credit_score || 0} size="sm"/><div className="min-w-0 flex-1"><div className="flex items-center gap-2"><h3 className="truncate text-sm font-bold">{customer.company_name}</h3>{customer.identity_verified ? <CheckCircle2 size={14} className="text-teal-600"/> : <ShieldQuestion size={14} className="text-amber-500"/>}</div><p className="mt-1 text-[10px] text-slate-400">{customer.name} · {customer.country}</p><div className="mt-3 flex flex-wrap gap-1.5"><Badge tone={customer.current_credit_score !== null && customer.current_credit_score < 60 ? 'high' : 'success'}>{customer.credit_risk_level || '待评分'}</Badge><Badge>{customer.transaction_count} 笔交易</Badge>{customer.watchlist_status && <Badge tone="medium">观察名单</Badge>}{customer.blacklist_status && <Badge tone="critical">黑名单</Badge>}</div></div></Card></Link>)}</div>
      <div className="mt-5 flex items-center justify-between text-xs text-slate-500"><span>共 {query.data?.total} 个外商</span><div className="flex items-center gap-2"><Button variant="outline" size="icon" disabled={page <= 1} onClick={() => setPage(value => value - 1)}><ChevronLeft size={15}/></Button><span>{page} / {query.data?.pages}</span><Button variant="outline" size="icon" disabled={page >= (query.data?.pages || 1)} onClick={() => setPage(value => value + 1)}><ChevronRight size={15}/></Button></div></div>
    </>}

    {open && <div className="fixed inset-0 z-[100] grid place-items-center bg-slate-950/45 p-4"><Card className="max-h-[92vh] w-full max-w-2xl overflow-auto"><div className="flex items-start justify-between border-b border-slate-100 p-5"><div><h2 className="font-bold">新增外商档案</h2><p className="mt-1 text-[10px] text-slate-400">保存后生成低置信度初始信用评分，可在交易积累后重算</p></div><button aria-label="关闭" onClick={() => setOpen(false)}><X size={19}/></button></div><div className="grid gap-4 p-5 sm:grid-cols-2">
      {[['name', '联系人姓名'], ['company_name', '企业名称'], ['country', '国家'], ['region', '地区'], ['registration_number', '企业注册号'], ['email', '邮箱'], ['phone', '电话'], ['industry', '行业'], ['main_product_category', '主营品类'], ['cooperation_start_date', '合作开始日期']].map(([key, label]) => <label key={key}><span className="mb-1.5 block text-[10px] font-semibold text-slate-500">{label}</span><Input type={key === 'cooperation_start_date' ? 'date' : key === 'email' ? 'email' : 'text'} value={String(form[key as keyof typeof form])} onChange={event => setForm({ ...form, [key]: event.target.value })}/></label>)}
      <label className="sm:col-span-2"><span className="mb-1.5 block text-[10px] font-semibold text-slate-500">备注</span><Textarea rows={3} value={form.notes} onChange={event => setForm({ ...form, notes: event.target.value })}/></label>
      <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={form.identity_verified} onChange={event => setForm({ ...form, identity_verified: event.target.checked })}/>身份已核验</label>
      <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={form.watchlist_status} onChange={event => setForm({ ...form, watchlist_status: event.target.checked })}/>加入观察名单</label>
    </div><div className="flex justify-end gap-2 border-t border-slate-100 p-5"><Button variant="outline" onClick={() => setOpen(false)}>取消</Button><Button disabled={create.isPending || !form.name || !form.company_name || !form.country} onClick={() => create.mutate()}>{create.isPending ? '正在保存…' : '保存并评分'}</Button></div></Card></div>}
  </div>
}
