import type { ChatMessage as Message } from '../../hooks/useChat'

export function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`chat-msg ${isUser ? 'chat-msg--user' : 'chat-msg--ai'}`}>
      <div
        className={`chat-msg-bubble ${message.isError ? 'chat-msg-bubble--error' : ''}`}
      >
        {message.pending ? (
          <span className="chat-pending">
            <span className="chat-typing" aria-label="生成中">
              <span />
              <span />
              <span />
            </span>
            {message.phaseText ? (
              <span className="chat-phase">{message.phaseText}</span>
            ) : null}
          </span>
        ) : (
          message.content
        )}
      </div>
    </div>
  )
}
