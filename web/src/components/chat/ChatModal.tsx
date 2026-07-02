import { Send, Sparkles, Trash2, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { ChatSize, useChat } from '../../hooks/useChat'
import { ChatMessage } from './ChatMessage'

type ChatState = ReturnType<typeof useChat>

const SIZES: { key: ChatSize; label: string }[] = [
  { key: 'sm', label: 'S' },
  { key: 'md', label: 'M' },
  { key: 'lg', label: 'L' },
]

export function ChatModal({ chat }: { chat: ChatState }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.messages])

  if (!chat.isOpen) return null

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void chat.send()
    }
  }

  return (
    <div className="chat-overlay" role="dialog" aria-label="AIアシスタント">
      <div className={`chat-modal chat-modal--${chat.size}`}>
        <header className="chat-header">
          <div className="chat-title">
            <Sparkles size={16} />
            <span>AIアシスタント</span>
          </div>
          <div className="chat-header-actions">
            <div className="chat-size-toggle" role="group" aria-label="サイズ切替">
              {SIZES.map((s) => (
                <button
                  key={s.key}
                  type="button"
                  className={chat.size === s.key ? 'active' : ''}
                  onClick={() => chat.setSize(s.key)}
                  aria-pressed={chat.size === s.key}
                >
                  {s.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="chat-icon-btn"
              onClick={chat.clear}
              disabled={chat.messages.length === 0}
              aria-label="会話をクリア"
              title="会話をクリア"
            >
              <Trash2 size={16} />
            </button>
            <button
              type="button"
              className="chat-icon-btn"
              onClick={chat.close}
              aria-label="閉じる"
              title="閉じる"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        <div className="chat-body">
          {chat.messages.length === 0 ? (
            <div className="chat-empty">
              <Sparkles size={28} />
              <p>投資の疑問や気になる銘柄について質問できます</p>
              <span className="chat-empty-note">
                ※ エージェント接続は今後のフェーズで実装予定
              </span>
            </div>
          ) : (
            chat.messages.map((m) => <ChatMessage key={m.id} message={m} />)
          )}
          <div ref={bottomRef} />
        </div>

        <footer className="chat-footer">
          <textarea
            className="chat-input"
            placeholder="メッセージを入力（Enterで送信 / Shift+Enterで改行）"
            value={chat.input}
            onChange={(e) => chat.setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
          />
          <button
            type="button"
            className="chat-send"
            onClick={() => void chat.send()}
            disabled={chat.busy || !chat.input.trim()}
            aria-label="送信"
          >
            <Send size={16} />
          </button>
        </footer>
      </div>
    </div>
  )
}
