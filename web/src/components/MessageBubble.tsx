import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { ChatMessage } from '../hooks/useStocksAdvisor'
import { AgentProgress } from './AgentProgress'

interface Props {
  message: ChatMessage
}

export function MessageBubble({ message }: Props) {
  const [showLog, setShowLog] = useState(false)
  const isUser = message.role === 'user'
  const isWorking =
    !isUser && message.status && !['done', 'error'].includes(message.status)
  const hasLog = !isUser && !isWorking && (message.progress?.length ?? 0) > 0

  return (
    <div className={`message-row ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && <div className="avatar">AI</div>}
      <div
        className={`bubble ${isUser ? 'bubble-user' : 'bubble-assistant'} ${
          message.isError ? 'bubble-error' : ''
        }`}
      >
        {isWorking ? (
          <AgentProgress status={message.status!} progress={message.progress} />
        ) : isUser ? (
          <div className="bubble-content">{message.content}</div>
        ) : (
          <>
            {hasLog && (
              <div className="agent-log">
                <button
                  type="button"
                  className="agent-log-toggle"
                  onClick={() => setShowLog((v) => !v)}
                >
                  {showLog ? (
                    <ChevronDown size={13} />
                  ) : (
                    <ChevronRight size={13} />
                  )}
                  エージェント実行ログ
                </button>
                {showLog && (
                  <AgentProgress
                    status={message.status!}
                    progress={message.progress}
                  />
                )}
              </div>
            )}
            <div className="bubble-content markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
