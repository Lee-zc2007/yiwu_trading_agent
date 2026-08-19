'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  History,
  LoaderCircle,
  MessageSquareText,
  Plus,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserRound,
  Workflow,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { AgentAnalysisPanel } from '@/components/agent/analysis-panel'
import { AgentMarkdown } from '@/components/agent/agent-markdown'
import { PageHeader } from '@/components/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Select, Textarea } from '@/components/ui/input'
import { api } from '@/lib/api'
import type {
  AgentResponse,
  ConversationHistory,
  ConversationSummary,
  ConversationToolCall,
  Customer,
  Paginated,
} from '@/lib/types'
import { dateTime } from '@/lib/utils'

type ChatMessage = {
  key: string
  role: 'user' | 'assistant'
  content: string
  response?: AgentResponse
}

type ChatPayload = {
  message: string
  customerId: number | null
  conversationId: string
}

const WELCOME_MESSAGE: ChatMessage = {
  key: 'welcome',
  role: 'assistant',
  content: '交易授信助手已就绪。你可以直接描述订单金额、定金和账期；我会逐项补齐关键信息，再调用确定性风控服务计算敞口、证据完整度与建议交易条件。',
}

function historyMessages(history: ConversationHistory): ChatMessage[] {
  return history.messages
    .filter((item) => item.role === 'user' || item.role === 'assistant')
    .map((item) => ({
      key: `history-${item.id ?? item.created_at}`,
      role: item.role as 'user' | 'assistant',
      content: item.content,
    }))
}

function latestHistoricalCalls(history: ConversationHistory | undefined): ConversationToolCall[] {
  if (!history) return []
  const message = [...history.messages].reverse().find((item) => item.role === 'assistant' && item.tool_calls.length)
  return message?.tool_calls ?? []
}

export function AgentPage() {
  const queryClient = useQueryClient()
  const [customerId, setCustomerId] = useState('')
  const [input, setInput] = useState('一个迪拜客户第一次合作，准备做3万美元订单，希望给45天账期。')
  const [selectedConversationId, setSelectedConversationId] = useState<string | null | undefined>(undefined)
  const [draftMessages, setDraftMessages] = useState<ChatMessage[]>([])
  const [lastResponse, setLastResponse] = useState<AgentResponse | null>(null)
  const chatBottomRef = useRef<HTMLDivElement>(null)

  const customers = useQuery({
    queryKey: ['agent-customers'],
    queryFn: () => api<Paginated<Customer>>('/api/customers?page_size=100'),
  })
  const conversations = useQuery({
    queryKey: ['agent-conversations'],
    queryFn: () => api<ConversationSummary[]>('/api/agent/conversations'),
  })
  const activeConversationId = selectedConversationId === undefined
    ? conversations.data?.[0]?.conversation_id ?? null
    : selectedConversationId
  const history = useQuery({
    queryKey: ['agent-history', activeConversationId],
    queryFn: () => api<ConversationHistory>(`/api/agent/history/${activeConversationId}`),
    enabled: Boolean(activeConversationId),
  })
  const displayedMessages = useMemo(() => {
    if (draftMessages.length) return draftMessages
    if (history.data?.conversation_id === activeConversationId && history.data.messages.length) return historyMessages(history.data)
    return [WELCOME_MESSAGE]
  }, [draftMessages, history.data, activeConversationId])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [displayedMessages, history.isLoading])

  const chat = useMutation({
    mutationFn: (payload: ChatPayload) => api<AgentResponse>('/api/agent/chat', {
      method: 'POST',
      body: JSON.stringify({
        message: payload.message,
        customer_id: payload.customerId,
        conversation_id: payload.conversationId,
      }),
    }),
    onMutate: (payload) => {
      setLastResponse(null)
      const historyBase = history.data?.conversation_id === activeConversationId ? historyMessages(history.data) : []
      setDraftMessages((current) => [
        ...(current.length ? current : historyBase).filter((item) => item.key !== 'welcome'),
        { key: `user-${Date.now()}`, role: 'user', content: payload.message },
      ])
    },
    onSuccess: (response) => {
      setSelectedConversationId(response.conversation_id)
      setDraftMessages((current) => [
        ...current,
        { key: `assistant-${Date.now()}`, role: 'assistant', content: response.answer, response },
      ])
      setLastResponse(response)
      queryClient.invalidateQueries({ queryKey: ['agent-conversations'] })
      queryClient.invalidateQueries({ queryKey: ['agent-history', response.conversation_id] })
    },
    onError: (error: Error) => {
      setDraftMessages((current) => [
        ...current,
        { key: `error-${Date.now()}`, role: 'assistant', content: `风控系统调用失败：${error.message}` },
      ])
    },
  })

  const deleteConversation = useMutation({
    mutationFn: (conversationId: string) => api<{ conversation_id: string }>(`/api/agent/conversations/${conversationId}`, {
      method: 'DELETE',
    }),
    onSuccess: (_, deletedId) => {
      queryClient.removeQueries({ queryKey: ['agent-history', deletedId] })
      queryClient.invalidateQueries({ queryKey: ['agent-conversations'] })
      if (deletedId === activeConversationId) {
        setSelectedConversationId(null)
        setDraftMessages([])
        setLastResponse(null)
      }
      toast.success('历史会话及其决策上下文已删除')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const selectedCustomer = customers.data?.items.find((item) => String(item.id) === customerId)
  const historicalCalls = useMemo(() => latestHistoricalCalls(history.data), [history.data])

  const submit = (message = input, customerOverride?: number | null) => {
    const trimmed = message.trim()
    if (!trimmed || chat.isPending) return
    const selectedId = customerId ? Number(customerId) : null
    setInput('')
    chat.mutate({
      message: trimmed,
      customerId: customerOverride === undefined ? selectedId : customerOverride,
      conversationId: activeConversationId ?? '',
    })
  }

  const newConversation = () => {
    if (chat.isPending) return
    setSelectedConversationId(null)
    setDraftMessages([])
    setLastResponse(null)
    setInput('一个迪拜客户第一次合作，准备做3万美元订单，希望给45天账期。')
  }

  const selectConversation = (conversationId: string) => {
    if (chat.isPending || conversationId === activeConversationId) return
    const selected = conversations.data?.find((item) => item.conversation_id === conversationId)
    setSelectedConversationId(conversationId)
    if (selected?.customer_id) setCustomerId(String(selected.customer_id))
    setLastResponse(null)
    setDraftMessages([])
  }

  const requestDeleteConversation = (conversationId: string, title: string) => {
    if (chat.isPending || deleteConversation.isPending) return
    if (!window.confirm(`确定删除历史会话“${title || '未命名会话'}”吗？此操作无法撤销。`)) return
    deleteConversation.mutate(conversationId)
  }

  const quickQuestions = [
    {
      label: '这笔订单账能放吗？',
      icon: Search,
      action: () => submit('这笔订单账能放吗？'),
    },
    {
      label: '还缺哪些关键信息？',
      icon: ClipboardCheck,
      action: () => submit('还缺哪些关键信息？'),
    },
    {
      label: '为什么当前风险敞口这么高？',
      icon: Search,
      action: () => submit('为什么当前风险敞口这么高？'),
    },
    {
      label: '如果定金提高到40%呢？',
      icon: Sparkles,
      action: () => submit('如果定金提高到40%呢？'),
    },
    {
      label: '如果把账期缩短到30天呢？',
      icon: Clock3,
      action: () => submit('如果把账期缩短到30天呢？'),
    },
    {
      label: '生成交易核验清单',
      icon: ClipboardCheck,
      action: () => submit('生成交易核验清单'),
    },
  ]

  return (
    <div>
      <PageHeader
        eyebrow="AI RISK OPERATIONS DESK"
        title="企业交易授信与风控助手"
        description="先补齐交易 Context，再编排客户可信度、交易规则、风险敞口、证据与授信条件；每条结论均可回溯。"
        actions={(
          <div className="flex items-center gap-2">
            <Badge tone="success" className="rounded-md">受控只读工具</Badge>
            <Badge className="rounded-md">{lastResponse?.mode || 'DEEPSEEK FIRST'}</Badge>
          </div>
        )}
      />

      <div className="grid min-h-[660px] gap-3 xl:h-[calc(100vh-210px)] xl:min-h-[660px] xl:grid-cols-[220px_minmax(0,1fr)_340px] 2xl:grid-cols-[250px_minmax(0,1fr)_370px]">
        <Card className="flex min-h-0 flex-col overflow-hidden rounded-none">
          <div className="border-b border-slate-200 bg-slate-50 px-3 py-3">
            <Button className="w-full rounded-md" size="sm" onClick={newConversation} disabled={chat.isPending}>
              <Plus size={14} />新建风控会话
            </Button>
          </div>
          <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2.5">
            <div className="flex items-center gap-2">
              <History size={13} className="text-slate-400" />
              <span className="text-[9px] font-bold tracking-[.12em] text-slate-500">历史会话</span>
            </div>
            <span className="text-[8px] text-slate-400">{conversations.data?.length ?? 0} 条</span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {conversations.isLoading ? (
              <div className="flex items-center gap-2 px-4 py-6 text-[10px] text-slate-400">
                <LoaderCircle size={13} className="animate-spin" />正在恢复会话
              </div>
            ) : conversations.data?.length ? (
              <div className="divide-y divide-slate-100">
                {conversations.data.map((conversation) => {
                  const active = activeConversationId === conversation.conversation_id
                  return (
                    <div
                      key={conversation.conversation_id}
                      className={`group relative transition ${active ? 'bg-teal-50/80' : 'hover:bg-slate-50'}`}
                    >
                      {active && <span className="absolute inset-y-0 left-0 w-0.5 bg-teal-600" />}
                      <button
                        onClick={() => selectConversation(conversation.conversation_id)}
                        className="w-full px-3 py-3 pr-9 text-left"
                      >
                      <div className="flex items-start gap-2">
                        <span className={`mt-0.5 grid size-6 shrink-0 place-items-center border ${active ? 'border-teal-200 bg-white text-teal-700' : 'border-slate-200 bg-slate-50 text-slate-400'}`}>
                          <MessageSquareText size={12} />
                        </span>
                        <div className="min-w-0 flex-1">
                          <strong className="block truncate text-[10px] text-slate-700">{conversation.title || '未命名会话'}</strong>
                          <div className="mt-1.5 flex items-center justify-between text-[8px] text-slate-400">
                            <span>{conversation.message_count} 条消息</span>
                            <span>{dateTime(conversation.updated_at)}</span>
                          </div>
                          {conversation.customer_id && <span className="mt-1.5 inline-block bg-slate-100 px-1.5 py-0.5 text-[7px] text-slate-500">客户 #{conversation.customer_id}</span>}
                        </div>
                      </div>
                      </button>
                      <button
                        type="button"
                        title="删除历史会话"
                        aria-label={`删除会话 ${conversation.title || '未命名会话'}`}
                        onClick={() => requestDeleteConversation(conversation.conversation_id, conversation.title)}
                        disabled={deleteConversation.isPending || chat.isPending}
                        className="absolute right-2 top-3 grid size-6 place-items-center text-slate-300 transition hover:bg-red-50 hover:text-red-600 disabled:opacity-40"
                      >
                        {deleteConversation.isPending && deleteConversation.variables === conversation.conversation_id
                          ? <LoaderCircle size={12} className="animate-spin" />
                          : <Trash2 size={12} />}
                      </button>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="px-4 py-8 text-center text-[10px] leading-5 text-slate-400">
                <MessageSquareText className="mx-auto mb-2" size={20} />
                暂无历史会话<br />发起分析后自动保存
              </div>
            )}
          </div>
          <div className="border-t border-slate-200 bg-[#f7f9f9] p-3">
            <div className="flex gap-2 text-[8px] leading-4 text-slate-500">
              <ShieldCheck size={14} className="mt-0.5 shrink-0 text-teal-700" />
              <p>会话按商户和用户隔离，敏感联系方式、地址及凭证在入库前脱敏。</p>
            </div>
          </div>
        </Card>

        <main className="flex min-h-[660px] min-w-0 flex-col overflow-hidden border border-slate-200 bg-white shadow-[0_3px_18px_rgba(15,23,42,.04)] xl:min-h-0">
          <div className="border-b border-slate-200 px-4 py-3">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <div className="flex min-w-0 items-center gap-3">
                <span className="grid size-9 shrink-0 place-items-center bg-[#0d4f4b] text-white">
                  <Bot size={18} />
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <strong className="text-xs text-slate-800">TradeGuard 风控决策助手</strong>
                    <span className="size-1.5 rounded-full bg-emerald-500" />
                  </div>
                  <p className="mt-0.5 truncate text-[8px] text-slate-400">
                    会话 {activeConversationId ? activeConversationId.slice(0, 12) : '待创建'} · Agent 不直接访问数据库
                  </p>
                </div>
              </div>
              <label className="ml-auto flex items-center gap-2 lg:w-[260px]">
                <span className="shrink-0 text-[9px] font-semibold text-slate-500">分析对象</span>
                <Select value={customerId} onChange={(event) => setCustomerId(event.target.value)} className="h-9 rounded-md text-[10px]">
                  <option value="">全局风险视角</option>
                  {customers.data?.items.map((customer) => (
                    <option value={customer.id} key={customer.id}>#{customer.id} {customer.company_name}</option>
                  ))}
                </Select>
              </label>
            </div>
          </div>

          <div className={`flex items-center gap-3 border-b px-4 py-2.5 ${chat.isPending ? 'border-amber-200 bg-amber-50' : 'border-teal-100 bg-teal-50/60'}`}>
            {chat.isPending ? <LoaderCircle size={14} className="animate-spin text-amber-600" /> : <Workflow size={14} className="text-teal-700" />}
            <div className="min-w-0 flex-1">
              <strong className={`block text-[10px] ${chat.isPending ? 'text-amber-800' : 'text-teal-800'}`}>
                {chat.isPending ? 'AI 正在调用风控系统分析' : '风控工具链待命'}
              </strong>
              <span className={`text-[8px] ${chat.isPending ? 'text-amber-600' : 'text-teal-700/60'}`}>
                {chat.isPending ? 'Context 抽取 → 缺失检查 → 风控工具 → 决策证据 → 条件建议' : '所有风险与敞口结论必须引用确定性工具结果'}
              </span>
            </div>
            {lastResponse && !chat.isPending && <Badge tone="success" className="rounded-sm px-2 py-0.5 text-[8px]">{lastResponse.tools_used.length} TOOLS VERIFIED</Badge>}
          </div>

          <div className="border-b border-slate-100 px-4 py-3">
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              <span className="shrink-0 text-[8px] font-bold tracking-[.12em] text-slate-400">快捷分析</span>
              {quickQuestions.map((question) => (
                <button
                  key={question.label}
                  onClick={question.action}
                  disabled={chat.isPending}
                  className="inline-flex h-7 shrink-0 items-center gap-1.5 border border-slate-200 bg-white px-2.5 text-[8px] font-semibold text-slate-600 hover:border-teal-400 hover:bg-teal-50 hover:text-teal-800 disabled:opacity-50"
                >
                  <question.icon size={11} />{question.label}
                </button>
              ))}
            </div>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto bg-[#f7f9f9] px-4 py-5">
            {history.isLoading && activeConversationId ? (
              <div className="flex items-center justify-center gap-2 py-10 text-[10px] text-slate-400">
                <LoaderCircle size={14} className="animate-spin" />正在恢复脱敏对话上下文
              </div>
            ) : (
              <div className="mx-auto max-w-3xl space-y-5">
                {displayedMessages.map((message) => message.role === 'user' ? (
                  <article key={message.key} className="ml-auto max-w-[82%] border-r-2 border-[#164e4a] bg-white px-4 py-3 shadow-sm">
                    <div className="mb-2 flex items-center justify-end gap-2 text-[8px] font-bold tracking-[.12em] text-slate-400">
                      ANALYST REQUEST
                      <span className="grid size-5 place-items-center bg-slate-100 text-slate-500"><UserRound size={11} /></span>
                    </div>
                    <p className="text-right text-[11px] leading-6 text-slate-700 whitespace-pre-wrap">{message.content}</p>
                  </article>
                ) : (
                  <article key={message.key} className="max-w-[92%] border-l-2 border-teal-600 bg-white shadow-sm">
                    <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <span className="grid size-6 place-items-center bg-teal-50 text-teal-700"><Bot size={13} /></span>
                        <div>
                          <span className="block text-[8px] font-bold tracking-[.14em] text-teal-700">AGENT RISK MEMO</span>
                          <span className="text-[7px] text-slate-400">系统证据约束回答</span>
                        </div>
                      </div>
                      {message.response && (
                        <div className="flex gap-1">
                          <Badge tone="success" className="rounded-sm px-1.5 py-0.5 text-[7px]">{message.response.mode}</Badge>
                          <Badge className="rounded-sm px-1.5 py-0.5 text-[7px]">{message.response.intent}</Badge>
                        </div>
                      )}
                    </div>
                    <AgentMarkdown content={message.content} />
                    {message.response && (
                      <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 bg-slate-50/70 px-4 py-2 text-[8px] text-slate-400">
                        <span className="flex items-center gap-1"><CheckCircle2 size={10} className="text-emerald-600" />{message.response.tools_used.length} 个工具已验证</span>
                        <span>{message.response.evidence.length} 条证据引用</span>
                        <span>{message.response.call_chain.length} 个执行节点</span>
                      </div>
                    )}
                  </article>
                ))}

                {chat.isPending && (
                  <article className="max-w-[92%] border-l-2 border-amber-500 bg-white shadow-sm">
                    <div className="flex items-center gap-3 px-4 py-4">
                      <span className="relative grid size-8 place-items-center bg-amber-50 text-amber-700">
                        <Sparkles size={15} className="animate-pulse" />
                        <span className="absolute -right-1 -top-1 size-2 animate-ping rounded-full bg-amber-400" />
                      </span>
                      <div>
                        <strong className="block text-[10px] text-slate-700">AI 正在调用风控系统分析</strong>
                        <div className="mt-1 flex items-center gap-1 text-[8px] text-slate-400">
                          <span>交易 Context</span><ChevronRight size={9} /><span>风险敞口</span><ChevronRight size={9} /><span>建议条件</span>
                        </div>
                      </div>
                    </div>
                  </article>
                )}
                <div ref={chatBottomRef} />
              </div>
            )}
          </div>

          <div className="border-t border-slate-200 bg-white p-4">
            <div className="border border-slate-300 focus-within:border-teal-500 focus-within:ring-2 focus-within:ring-teal-500/10">
              <Textarea
                rows={3}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault()
                    submit()
                  }
                }}
                placeholder="描述订单金额、币种、定金、账期、合同、付款主体或保障条件……"
                className="resize-none rounded-none border-0 text-[11px] leading-5 focus:border-0"
              />
              <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2">
                <div className="flex items-center gap-2 text-[8px] text-slate-400">
                  <ShieldCheck size={11} className="text-teal-600" />
                  <span>{selectedCustomer ? `当前分析：${selectedCustomer.company_name}` : '当前为全局风险视角'}</span>
                  <span className="hidden sm:inline">· Enter 发送 / Shift+Enter 换行</span>
                </div>
                <Button size="sm" className="h-7 rounded-sm px-3 text-[9px]" onClick={() => submit()} disabled={!input.trim() || chat.isPending}>
                  {chat.isPending ? <LoaderCircle size={12} className="animate-spin" /> : <Send size={12} />}
                  提交分析
                </Button>
              </div>
            </div>
          </div>
        </main>

        <AgentAnalysisPanel
          response={lastResponse}
          historicalCalls={historicalCalls}
          pending={chat.isPending}
          customerName={selectedCustomer?.company_name}
        />
      </div>

      <div className="mt-3 flex flex-col gap-2 border border-slate-200 bg-white px-4 py-3 text-[8px] text-slate-400 sm:flex-row sm:items-center sm:justify-between">
        <span className="flex items-center gap-1.5"><ShieldCheck size={11} className="text-teal-600" />Agent 不自动批准或拒绝授信，条件调整只做模拟，最终决策由商户确认。</span>
        <span className="flex items-center gap-1.5"><Clock3 size={11} />会话和工具调用已脱敏持久化</span>
      </div>
    </div>
  )
}
