'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { AlertTriangle, Bot, ChevronRight, FileSearch, Gauge, Menu, Radar, ShieldCheck, Users, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/store/app-store'

const nav=[
  {href:'/dashboard',label:'风控总览',caption:'风险态势与关键指标',icon:Gauge},
  {href:'/customers',label:'外商档案',caption:'信用画像与交易历史',icon:Users},
  {href:'/transactions',label:'交易管理',caption:'订单与批量导入',icon:FileSearch},
  {href:'/risk-check',label:'新订单检测',caption:'路演核心风控流程',icon:Radar},
  {href:'/alerts',label:'预警中心',caption:'证据与处置闭环',icon:AlertTriangle},
  {href:'/agent',label:'AI 风控 Agent',caption:'工具调用与解释',icon:Bot},
  {href:'/demo-scenarios',label:'演示场景',caption:'六类稳定风险样例',icon:ShieldCheck},
]

export function AppShell({children}:{children:React.ReactNode}){const path=usePathname();const {sidebarOpen,setSidebarOpen}=useAppStore();return <div className="min-h-screen bg-[#f4f7f7] text-slate-900">
  <aside className={cn('fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-[#0b2e2d] text-white transition-transform lg:translate-x-0',sidebarOpen?'translate-x-0':'-translate-x-full')}>
    <div className="flex h-20 items-center gap-3 border-b border-white/10 px-5"><div className="grid size-10 place-items-center rounded-xl bg-teal-400 text-[#07302e]"><ShieldCheck size={23}/></div><div><strong className="block text-[15px]">TradeGuard AI</strong><span className="text-[10px] tracking-[.14em] text-teal-100/60">外贸风控智能体</span></div><button aria-label="关闭导航" onClick={()=>setSidebarOpen(false)} className="ml-auto lg:hidden"><X size={19}/></button></div>
    <div className="mx-4 mt-4 rounded-lg border border-white/10 bg-white/5 px-3 py-2.5"><div className="flex items-center gap-2 text-xs text-teal-50"><i className="size-2 rounded-full bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,.12)]"/>系统运行正常</div><p className="mt-1 text-[10px] text-teal-100/55">Mock Agent · 本地模型已启用</p></div>
    <nav className="mt-4 flex-1 space-y-1 px-3">{nav.map(item=>{const active=path===item.href||path.startsWith(item.href+'/');return <Link key={item.href} href={item.href} onClick={()=>setSidebarOpen(false)} className={cn('group flex items-center gap-3 rounded-lg px-3 py-2.5 text-teal-50/70 hover:bg-white/7 hover:text-white',active&&'bg-teal-400/15 text-teal-200 ring-1 ring-teal-300/10')}><item.icon size={18}/><div className="min-w-0 flex-1"><strong className="block text-xs">{item.label}</strong><span className="block truncate text-[9px] opacity-55">{item.caption}</span></div><ChevronRight size={13} className="opacity-0 group-hover:opacity-70"/></Link>})}</nav>
    <div className="m-4 rounded-lg bg-[#082523] p-3 text-[10px] leading-5 text-teal-100/55">辅助决策系统<br/><span className="text-teal-200/80">高风险操作必须人工确认</span></div>
  </aside>{sidebarOpen&&<button aria-label="关闭导航遮罩" className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={()=>setSidebarOpen(false)}/>}
  <div className="lg:pl-64"><header className="sticky top-0 z-30 flex h-16 items-center border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur lg:px-7"><button aria-label="打开导航" onClick={()=>setSidebarOpen(true)} className="mr-3 lg:hidden"><Menu size={20}/></button><div><strong className="block text-xs">义乌远航贸易示范商户</strong><span className="text-[10px] text-slate-400">Merchant ID: 1 · 夏季社会实践路演环境</span></div><div className="ml-auto flex items-center gap-3"><span className="hidden rounded-full bg-amber-50 px-3 py-1 text-[10px] font-semibold text-amber-700 sm:block">DEMO DATA</span><div className="grid size-8 place-items-center rounded-full bg-teal-100 text-xs font-bold text-teal-700">义</div></div></header><main className="mx-auto max-w-[1600px] p-4 lg:p-7">{children}</main><footer className="flex flex-col gap-1 border-t border-slate-200 px-7 py-5 text-[10px] text-slate-400 sm:flex-row sm:justify-between"><span>风险评分和模型结果仅供辅助判断，最终决策应由商户结合实际情况作出。</span><span>TradeGuard AI v1.0</span></footer></div>
</div>}
