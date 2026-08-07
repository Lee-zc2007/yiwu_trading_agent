import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
export function Input({className,...props}:InputHTMLAttributes<HTMLInputElement>){return <input className={cn('h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none placeholder:text-slate-400 focus:border-teal-500 focus:ring-2 focus:ring-teal-500/10',className)} {...props}/>} 
export function Select({className,...props}:SelectHTMLAttributes<HTMLSelectElement>){return <select className={cn('h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-teal-500',className)} {...props}/>} 
export function Textarea({className,...props}:TextareaHTMLAttributes<HTMLTextAreaElement>){return <textarea className={cn('w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-teal-500',className)} {...props}/>} 
