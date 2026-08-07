import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

const variants = cva('inline-flex items-center justify-center gap-2 rounded-lg text-sm font-semibold transition disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-500', { variants:{ variant:{ default:'bg-teal-600 text-white hover:bg-teal-700 shadow-sm', outline:'border border-slate-200 bg-white hover:border-teal-500 hover:text-teal-700', ghost:'hover:bg-slate-100', danger:'bg-red-600 text-white hover:bg-red-700' }, size:{ default:'h-10 px-4', sm:'h-8 px-3 text-xs', icon:'size-9' } }, defaultVariants:{variant:'default',size:'default'} })
export function Button({className,variant,size,asChild=false,...props}:ButtonHTMLAttributes<HTMLButtonElement>&VariantProps<typeof variants>&{asChild?:boolean}) { const Comp=asChild?Slot:'button'; return <Comp className={cn(variants({variant,size}),className)} {...props}/> }
