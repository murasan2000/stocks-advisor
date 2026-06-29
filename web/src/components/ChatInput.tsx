import { type FormEvent, type KeyboardEvent } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  onSend: (query: string) => void
  disabled: boolean
}

export function ChatInput({ value, onChange, onSend, disabled }: Props) {
  const submit = (e?: FormEvent) => {
    e?.preventDefault()
    const query = value.trim()
    if (!query || disabled) return
    onSend(query)
    onChange('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form className="chat-input" onSubmit={submit}>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="銘柄や相場について質問する（例: トヨタ自動車の今後の見通しは？）"
        rows={1}
        disabled={disabled}
      />
      <button type="submit" disabled={disabled || !value.trim()} aria-label="送信">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path
            d="M5 12L3 21L21 12L3 3L5 12ZM5 12H12"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </form>
  )
}
