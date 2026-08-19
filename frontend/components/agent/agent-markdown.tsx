import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type AgentMarkdownProps = {
  content: string
}

/**
 * 安全渲染 Agent 的 Markdown/GFM 输出。
 * 不启用 raw HTML，屏蔽远程图片，并为链接增加隔离属性，避免模型输出成为注入入口。
 */
export function AgentMarkdown({ content }: AgentMarkdownProps) {
  return (
    <div className="min-w-0 px-4 py-3 text-[11px] leading-6 text-slate-700">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          h1: ({ children }) => <h1 className="mb-3 mt-1 text-base font-bold text-slate-900">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-2 mt-4 border-b border-slate-200 pb-1 text-sm font-bold text-slate-900 first:mt-0">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-1.5 mt-3 text-xs font-bold text-teal-800">{children}</h3>,
          p: ({ children }) => <p className="my-2 whitespace-pre-wrap first:mt-0 last:mb-0">{children}</p>,
          strong: ({ children }) => <strong className="font-bold text-slate-900">{children}</strong>,
          ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
          li: ({ children }) => <li className="pl-0.5">{children}</li>,
          blockquote: ({ children }) => <blockquote className="my-3 border-l-2 border-teal-500 bg-teal-50 px-3 py-2 text-slate-600">{children}</blockquote>,
          table: ({ children }) => <div className="my-3 overflow-x-auto"><table className="w-full min-w-[520px] border-collapse text-left text-[10px]">{children}</table></div>,
          thead: ({ children }) => <thead className="bg-slate-100 text-slate-700">{children}</thead>,
          th: ({ children }) => <th className="border border-slate-200 px-2 py-1.5 font-bold">{children}</th>,
          td: ({ children }) => <td className="border border-slate-200 px-2 py-1.5 align-top">{children}</td>,
          code: ({ children, className }) => className ? (
            <code className={`${className} text-[10px]`}>{children}</code>
          ) : (
            <code className="rounded-sm bg-slate-100 px-1 py-0.5 font-mono text-[10px] text-teal-800">{children}</code>
          ),
          pre: ({ children }) => <pre className="my-3 overflow-x-auto bg-slate-950 p-3 font-mono text-[10px] leading-5 text-slate-100">{children}</pre>,
          a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer noopener" className="font-semibold text-teal-700 underline underline-offset-2">{children}</a>,
          img: () => null,
          hr: () => <hr className="my-4 border-slate-200" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
