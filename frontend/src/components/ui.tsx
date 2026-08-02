import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Sparkles } from 'lucide-react'

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="page-header">
    <div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>
    {actions && <div className="page-actions">{actions}</div>}
  </div>
}

export function Card({ children, className = '', title, action }: { children: ReactNode; className?: string; title?: ReactNode; action?: ReactNode }) {
  return <section className={`card ${className}`}>
    {(title || action) && <div className="card-head"><h3>{title}</h3>{action}</div>}
    {children}
  </section>
}

export function Badge({ children, tone = 'neutral' }: { children: ReactNode; tone?: string }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function MetricCard({ label, value, suffix = '', prefix = '', change, tone = 'blue', icon }: { label: string; value: string | number; suffix?: string; prefix?: string; change?: string; tone?: string; icon?: ReactNode }) {
  return <div className={`metric metric-${tone}`}>
    <div className="metric-top"><span>{label}</span>{icon}</div>
    <strong>{prefix}{typeof value === 'number' && value >= 1000 ? value.toLocaleString() : value}{suffix}</strong>
    {change && <small>{change}</small>}
  </div>
}

export function DemoNotice({ children = '本页数据均为基于调研假设的 Demo 模拟值。' }: { children?: ReactNode }) {
  return <div className="demo-notice"><Sparkles size={15} />{children}</div>
}

export function Disclaimer({ children }: { children: ReactNode }) {
  return <div className="disclaimer"><AlertTriangle size={16} />{children}</div>
}

export function ProgressBar({ value, tone = 'blue' }: { value: number; tone?: string }) {
  return <div className="progress"><span className={`fill fill-${tone}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>
}

export function ScoreRing({ value, label, tone = 'blue' }: { value: number; label: string; tone?: string }) {
  return <div className={`score-ring ring-${tone}`} style={{ '--score': `${value * 3.6}deg` } as React.CSSProperties}><div><strong>{value}</strong><span>{label}</span></div></div>
}

export function EmptyState({ text }: { text: string }) {
  return <div className="empty"><CheckCircle2 size={24} /><span>{text}</span></div>
}

export function ProductVisual({ variant = 0, compact = false }: { variant?: number; compact?: boolean }) {
  return <div className={`product-visual visual-${variant % 5} ${compact ? 'compact' : ''}`} aria-label="产品概念视觉"><span className="shape-main" /><span className="shape-cap" /><span className="visual-glow" /></div>
}

export const toneForRisk = (value: string | number) => {
  if (typeof value === 'number') return value >= 80 ? 'danger' : value >= 60 ? 'orange' : value >= 30 ? 'warning' : 'success'
  return value.includes('极高') ? 'danger' : value.includes('高') ? 'orange' : value.includes('中') ? 'warning' : 'success'
}

