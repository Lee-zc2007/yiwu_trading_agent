import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }
export const money = (value: number, currency = 'USD') => new Intl.NumberFormat('zh-CN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value)
export const dateTime = (value: string) => new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
