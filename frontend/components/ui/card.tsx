import type { HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
export function Card({className,...props}:HTMLAttributes<HTMLDivElement>){return <div className={cn('rounded-xl border border-slate-200 bg-white shadow-[0_3px_18px_rgba(15,23,42,.04)]',className)} {...props}/>} 
export function CardHeader({className,...props}:HTMLAttributes<HTMLDivElement>){return <div className={cn('flex items-center justify-between border-b border-slate-100 px-5 py-4',className)} {...props}/>} 
export function CardContent({className,...props}:HTMLAttributes<HTMLDivElement>){return <div className={cn('p-5',className)} {...props}/>} 
