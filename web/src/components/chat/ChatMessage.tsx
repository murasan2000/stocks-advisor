import type { ChatMessage as Message } from '../../hooks/useChat'
import { AgentProgress } from './AgentProgress'

export function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user'
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
            {message.content}
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
