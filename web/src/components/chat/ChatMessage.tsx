import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage as Message } from '../../hooks/useChat'
import { AgentProgress } from './AgentProgress'

// AI 回答は Markdown で描画する。生 HTML は許可しない（XSS 対策）。
// リンクは別タブで開き、rel で opener を遮断する。
const MARKDOWN_COMPONENTS = {
  // href/children のみ引き回す（react-markdown が渡す node 等は DOM に流さない）。
  a: ({ href, children }: React.ComponentProps<'a'>) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
}

export function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  // AI の通常応答のみ Markdown 表示（ユーザー発言・エラーはプレーンのまま）。
  const asMarkdown = !isUser && !message.isError
  return (
    <div className={`chat-msg ${isUser ? 'chat-msg--user' : 'chat-msg--ai'}`}>
      <div
        className={`chat-msg-bubble ${message.isError ? 'chat-msg-bubble--error' : ''}`}
      >
        {message.pending ? (
          message.progress?.length ? (
            <AgentProgress steps={message.progress} />
          ) : (
            <span className="chat-pending">
              <span className="chat-typing" aria-label="生成中">
                <span />
                <span />
                <span />
              </span>
            </span>
          )
        ) : (
          <>
            {asMarkdown ? (
              <div className="md">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={MARKDOWN_COMPONENTS}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            ) : (
              message.content
            )}
            {/* エラー時はどのステップで失敗したかを残す */}
            {message.isError && message.progress?.length ? (
              <AgentProgress steps={message.progress} />
            ) : null}
          </>
        )}
      </div>
    </div>
  )
}
