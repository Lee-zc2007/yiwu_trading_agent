import { Inbox, LoaderCircle, TriangleAlert } from 'lucide-react'
export function Loading({text='正在读取风险数据…'}:{text?:string}){return <div className="grid min-h-48 place-items-center text-sm text-slate-400"><div className="flex items-center gap-2"><LoaderCircle className="animate-spin" size={18}/>{text}</div></div>}
export function Empty({text='暂无数据'}:{text?:string}){return <div className="grid min-h-40 place-items-center text-center text-sm text-slate-400"><div><Inbox className="mx-auto mb-2"/><p>{text}</p></div></div>}
export function ErrorState({message}:{message:string}){return <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"><TriangleAlert size={18}/>{message}</div>}
