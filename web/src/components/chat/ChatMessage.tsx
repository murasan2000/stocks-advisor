import type { ChatMessage as Message } from '../../hooks/useChat'

export function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`chat-msg ${isUser ? 'chat-msg--user' : 'chat-msg--ai'}`}>
      <div className="chat-msg-bubble">
        {message.pending ? (
          <span className="chat-typing" aria-label="生成中">
            <span />
            <span />
            <span />
          </span>
        ) : (
          message.content
        )}
      </div>
    </div>
  )
}
