import type { Metadata } from 'next'
import './globals.css'
import { Providers } from '@/components/providers'
import { AppShell } from '@/components/layout/app-shell'

export const metadata:Metadata={title:'TradeGuard AI 外贸风控智能体',description:'面向义乌外贸商户的信用评分、异常检测与证据型 AI Agent'}
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="zh-CN"><body><Providers><AppShell>{children}</AppShell></Providers></body></html>}
