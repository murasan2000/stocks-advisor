import { useCallback, useState } from 'react'

export type ChatSize = 'sm' | 'md' | 'lg'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  pending?: boolean
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

const uid = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : String(Date.now() + Math.random())

// Phase 4 以降でエージェント接続（Job作成→ポーリング）に差し替える暫定応答。
function mockReply(question: string): string {
  return (
    'AIエージェントは現在準備中です（Phase 4 以降で接続予定）。\n\n' +
    `ご質問「${question}」には、企業分析・一般質問エージェントの実装後にお答えします。`
  )
}

/**
 * チャットの状態管理。開閉・サイズ・入力内容・メッセージを保持する
 * （App 直下に置くことでモーダルを閉じても状態が維持される）。
 * 送信は現状モック応答。将来は送信→Job作成→進捗ポーリングに差し替える。
 */
export function useChat() {
  const [isOpen, setIsOpen] = useState(false)
  const [size, setSize] = useState<ChatSize>('md')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [busy, setBusy] = useState(false)

  const open = useCallback(() => setIsOpen(true), [])
  const close = useCallback(() => setIsOpen(false), [])
  const toggle = useCallback(() => setIsOpen((v) => !v), [])

  const send = useCallback(async () => {
    const text = input.trim()
    if (!text || busy) return
    const pendingId = uid()
    setMessages((prev) => [
      ...prev,
      { id: uid(), role: 'user', content: text },
      { id: pendingId, role: 'assistant', content: '', pending: true },
    ])
    setInput('')
    setBusy(true)
    try {
      // TODO(Phase 4/5): createJob → poll → stream/replace
      await sleep(600)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? { ...m, pending: false, content: mockReply(text) }
            : m,
        ),
      )
    } finally {
      setBusy(false)
    }
  }, [input, busy])

  const clear = useCallback(() => setMessages([]), [])

  return {
    isOpen,
    size,
    setSize,
    input,
    setInput,
    messages,
    busy,
    open,
    close,
    toggle,
    send,
    clear,
  }
}
