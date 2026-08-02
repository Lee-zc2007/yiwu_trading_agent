import { useEffect, useMemo, useState } from 'react'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  BarChart3, Bot, Box, BriefcaseBusiness, ChevronLeft, ChevronRight, ClipboardCheck,
  FileSearch, FileText, FlaskConical, Gauge, Globe2, Handshake, Languages, LayoutDashboard,
  Menu, Moon, PackageSearch, Play, RotateCcw, Settings, ShieldCheck, ShoppingBag, Sun,
  UsersRound, X,
} from 'lucide-react'
import { safeGet, safePost } from './api/client'
import { Badge } from './components/ui'
import { StoryPage, DashboardPage } from './pages/OverviewPages'
import { AssistantPage, CrmPage, ProductPage, QuotePage, ShowroomPage } from './pages/TradePages'
import { AfterSalesPage, ContractPage, ImpactPage, OrdersPage, ResearchPage, RiskPage, RoadshowPage, SettingsPage } from './pages/TrustPages'

const nav = [
  { to: '/', label: '项目首页', icon: Globe2 }, { to: '/dashboard', label: '老板驾驶舱', icon: LayoutDashboard },
  { to: '/products', label: 'AI产品设计', icon: Box }, { to: '/showroom', label: '3D数字展台', icon: PackageSearch },
  { to: '/assistant', label: 'AI销售助手', icon: Bot }, { to: '/crm', label: '客户与询盘', icon: UsersRound },
  { to: '/quotes', label: '智能报价', icon: FileText }, { to: '/risk', label: '数字信任中心', icon: ShieldCheck },
  { to: '/contracts', label: '合同审核', icon: FileSearch }, { to: '/orders', label: '订单与物流', icon: ShoppingBag },
  { to: '/after-sales', label: '售后分析', icon: Handshake }, { to: '/impact', label: '效果量化', icon: BarChart3 },
  { to: '/research', label: '调研成果', icon: FlaskConical }, { to: '/roadshow', label: '路演模式', icon: Play },
  { to: '/settings', label: '系统设置', icon: Settings },
]

export default function App() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [theme, setTheme] = useState(localStorage.getItem('yiwu-theme') || 'dark')
  const [role, setRole] = useState<'merchant' | 'buyer'>('merchant')
  const [live, setLive] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { t, i18n } = useTranslation()

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('yiwu-theme', theme)
  }, [theme])
  useEffect(() => { safeGet<any>('/health', {}).then(result => setLive(result.live)) }, [location.pathname])
  useEffect(() => setMobileOpen(false), [location.pathname])

  const context = useMemo(() => ({ live, role, setRole }), [live, role])

  return <div className={`app-shell ${collapsed ? 'nav-collapsed' : ''}`}>
    <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
      <div className="brand"><div className="brand-mark">义</div><div className="brand-copy"><strong>Yiwu AI</strong><span>Trade Copilot</span></div><button className="icon-btn mobile-only" onClick={() => setMobileOpen(false)} aria-label="关闭菜单"><X size={18} /></button></div>
      <div className="mode-panel"><span className="status-dot" /><div><strong>{t('demo')}</strong><small>{live ? '后端已连接' : '本地降级数据'}</small></div></div>
      <nav className="side-nav">{nav.map(item => <NavLink key={item.to} to={item.to} end={item.to === '/'} title={item.label}><item.icon size={18} /><span>{item.label}</span></NavLink>)}</nav>
      <button className="collapse-btn" onClick={() => setCollapsed(value => !value)}>{collapsed ? <ChevronRight size={18} /> : <><ChevronLeft size={18} /><span>收起导航</span></>}</button>
    </aside>
    {mobileOpen && <div className="nav-scrim" onClick={() => setMobileOpen(false)} />}
    <div className="workspace">
      <header className="topbar">
        <button className="icon-btn menu-btn" onClick={() => setMobileOpen(true)} aria-label="打开菜单"><Menu size={20} /></button>
        <div className="breadcrumb"><BriefcaseBusiness size={16} /><span>义乌国际商贸城 · AI数字信任实验室</span></div>
        <div className="top-actions">
          <div className="role-switch"><button className={role === 'merchant' ? 'active' : ''} onClick={() => setRole('merchant')}>商户</button><button className={role === 'buyer' ? 'active' : ''} onClick={() => setRole('buyer')}>采购商</button></div>
          <button className="icon-btn" title="中英文切换" onClick={() => i18n.changeLanguage(i18n.language === 'zh' ? 'en' : 'zh')}><Languages size={18} /></button>
          <button className="icon-btn" title="主题切换" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}</button>
          <Badge tone={live ? 'success' : 'warning'}>{live ? 'API LIVE' : 'OFFLINE DEMO'}</Badge>
          <button className="btn btn-primary top-pitch" onClick={() => navigate('/roadshow')}><Play size={15} />开始路演</button>
        </div>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<StoryPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/products" element={<ProductPage />} />
          <Route path="/showroom" element={<ShowroomPage role={context.role} />} />
          <Route path="/assistant" element={<AssistantPage />} />
          <Route path="/crm" element={<CrmPage />} />
          <Route path="/quotes" element={<QuotePage />} />
          <Route path="/risk" element={<RiskPage />} />
          <Route path="/contracts" element={<ContractPage />} />
          <Route path="/orders" element={<OrdersPage />} />
          <Route path="/after-sales" element={<AfterSalesPage />} />
          <Route path="/impact" element={<ImpactPage />} />
          <Route path="/research" element={<ResearchPage />} />
          <Route path="/roadshow" element={<RoadshowPage />} />
          <Route path="/settings" element={<SettingsPage live={live} onHealth={() => safeGet<any>('/health', {}).then(result => setLive(result.live))} onReset={() => safePost('/demo/reset', {}, { status: 'ok' })} />} />
        </Routes>
      </main>
      <footer className="app-footer"><span>虚构演示数据 · 社会实践成果原型</span><span>Yiwu AI Trade Copilot v1.0</span></footer>
    </div>
  </div>
}

