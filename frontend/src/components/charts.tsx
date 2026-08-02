import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Funnel, FunnelChart, LabelList,
  Legend, Line, LineChart, Pie, PieChart, Radar, RadarChart, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const tooltipStyle = { background: '#0d2239', border: '1px solid #294866', borderRadius: 10, color: '#f5f8fb', fontSize: 12 }
const grid = '#29435a66'
const tick = { fill: '#8298ad', fontSize: 11 }

export function TrendChart({ data }: { data: any[] }) {
  return <ResponsiveContainer width="100%" height="100%"><AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
    <defs><linearGradient id="blueArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#44a8ff" stopOpacity={.42} /><stop offset="100%" stopColor="#44a8ff" stopOpacity={0} /></linearGradient></defs>
    <CartesianGrid stroke={grid} vertical={false} /><XAxis dataKey="day" tick={tick} axisLine={false} tickLine={false} /><YAxis tick={tick} axisLine={false} tickLine={false} />
    <Tooltip contentStyle={tooltipStyle} /><Legend wrapperStyle={{ fontSize: 12 }} />
    <Area name="全部询盘" type="monotone" dataKey="inquiries" stroke="#44a8ff" strokeWidth={2.5} fill="url(#blueArea)" />
    <Line name="有效询盘" type="monotone" dataKey="valid" stroke="#31c6a4" strokeWidth={2} dot={{ r: 3 }} />
  </AreaChart></ResponsiveContainer>
}

export function DonutChart({ data }: { data: any[] }) {
  const colors = ['#44a8ff', '#31c6a4', '#8e7cff', '#ffb45c', '#ed6f83']
  return <ResponsiveContainer width="100%" height="100%"><PieChart><Tooltip contentStyle={tooltipStyle} /><Pie data={data} dataKey="value" nameKey="name" innerRadius="52%" outerRadius="78%" paddingAngle={3}>{data.map((item, i) => <Cell key={item.name} fill={item.color || colors[i % colors.length]} />)}</Pie><Legend verticalAlign="bottom" iconType="circle" wrapperStyle={{ fontSize: 11 }} /></PieChart></ResponsiveContainer>
}

export function HorizontalBars({ data, dataKey = 'value', color = '#44a8ff' }: { data: any[]; dataKey?: string; color?: string }) {
  return <ResponsiveContainer width="100%" height="100%"><BarChart data={data} layout="vertical" margin={{ top: 5, right: 20, left: 2, bottom: 0 }}><CartesianGrid stroke={grid} horizontal={false} /><XAxis type="number" tick={tick} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="name" tick={tick} axisLine={false} tickLine={false} width={62} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey={dataKey} fill={color} radius={[0, 6, 6, 0]} barSize={12} /></BarChart></ResponsiveContainer>
}

export function FunnelView({ data }: { data: any[] }) {
  return <ResponsiveContainer width="100%" height="100%"><FunnelChart><Tooltip contentStyle={tooltipStyle} /><Funnel dataKey="value" data={data} isAnimationActive><LabelList position="right" fill="#b9cad9" stroke="none" dataKey="name" /></Funnel></FunnelChart></ResponsiveContainer>
}

export function TimeCompareChart({ data }: { data: any[] }) {
  return <ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}><CartesianGrid stroke={grid} vertical={false} /><XAxis dataKey="task" tick={tick} axisLine={false} tickLine={false} /><YAxis tick={tick} axisLine={false} tickLine={false} /><Tooltip contentStyle={tooltipStyle} /><Legend wrapperStyle={{ fontSize: 11 }} /><Bar name="人工/分钟" dataKey="manual" fill="#647e98" radius={[5, 5, 0, 0]} /><Bar name="AI/分钟" dataKey="ai" fill="#31c6a4" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer>
}

export function SatisfactionChart({ data }: { data: any[] }) {
  return <ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{ top: 10, right: 12, left: -14, bottom: 0 }}><CartesianGrid stroke={grid} vertical={false} /><XAxis dataKey="month" tick={tick} axisLine={false} /><YAxis domain={[3.5, 5]} tick={tick} axisLine={false} /><Tooltip contentStyle={tooltipStyle} /><Line type="monotone" dataKey="score" stroke="#31c6a4" strokeWidth={3} dot={{ fill: '#31c6a4', r: 4 }} /></LineChart></ResponsiveContainer>
}

export function RiskRadar({ data }: { data: any[] }) {
  return <ResponsiveContainer width="100%" height="100%"><RadarChart data={data}><PolarGrid stroke={grid} /><PolarAngleAxis dataKey="name" tick={tick} /><Radar dataKey="contribution" stroke="#f4576c" fill="#f4576c" fillOpacity={.32} /><Tooltip contentStyle={tooltipStyle} /></RadarChart></ResponsiveContainer>
}

export function ImpactChart({ data }: { data: any[] }) {
  return <ResponsiveContainer width="100%" height="100%"><BarChart data={data}><CartesianGrid stroke={grid} vertical={false} /><XAxis dataKey="name" tick={tick} axisLine={false} /><YAxis tick={tick} axisLine={false} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="before" name="使用前" fill="#647e98" radius={[6, 6, 0, 0]} /><Bar dataKey="after" name="使用后" fill="#44a8ff" radius={[6, 6, 0, 0]} /><Legend wrapperStyle={{ fontSize: 11 }} /></BarChart></ResponsiveContainer>
}

