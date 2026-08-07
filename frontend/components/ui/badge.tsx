import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
const tones:Record<string,string>={low:'bg-emerald-50 text-emerald-700 ring-emerald-600/20',medium:'bg-amber-50 text-amber-700 ring-amber-600/20',high:'bg-orange-50 text-orange-700 ring-orange-600/20',critical:'bg-red-50 text-red-700 ring-red-600/20',neutral:'bg-slate-100 text-slate-600 ring-slate-500/20',success:'bg-teal-50 text-teal-700 ring-teal-600/20'}
export function Badge({className,tone='neutral',...props}:HTMLAttributes<HTMLSpanElement>&{tone?:string}){return <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset',tones[tone]||tones.neutral,className)} {...props}/>} 
export const riskLabel=(level:string)=>({low:'低风险',medium:'中风险',high:'高风险',critical:'严重风险'}[level]||level)
