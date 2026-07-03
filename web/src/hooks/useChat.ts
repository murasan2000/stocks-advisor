import { useCallback, useState } from 'react'
import {
  createConversation,
  deleteConversation,
  getConversations,
  getJob,
  getMessages,
  postMessage,
} from '../api/client'
import { type Conversation, PHASE_LABELS } from '../types/api'

/** モーダルの矩形。x/y は画面右下からのオフセット（右下アンカー）。 */
export interface ChatRect {
  w: number
  h: number
  x: number
  y: number
}

export const DEFAULT_CHAT_RECT: ChatRect = { w: 460, h: 620, x: 22, y: 22 }

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  pending?: boolean
  isError?: boolean
  phaseText?: string // 生成中の進捗表示（例: 「意図判定: 完了」）
}

const POLL_MS = 1200
const POLL_TIMEOUT_MS = 330_000 // バックエンドのエージェントタイムアウトより長め

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export type ChatView = 'chat' | 'history'

const uid = () =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : String(Date.now() + Math.random())

/**
 * チャットの状態管理。開閉・位置/サイズ・入力内容・メッセージを保持する
 * （App 直下に置くことでモーダルを閉じても状態が維持される）。
 * 会話・メッセージはバックエンド（/chat API）に永続化される。
 * 応答は現状サーバ側モック。将来は Job 作成→進捗ポーリングに差し替える。
 */
export function useChat() {
  const [isOpen, setIsOpen] = useState(false)
  const [rect, setRect] = useState<ChatRect>(DEFAULT_CHAT_RECT)
  const [view, setView] = useState<ChatView>('chat')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [busy, setBusy] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const open = useCallback(() => setIsOpen(true), [])
  const close = useCallback(() => setIsOpen(false), [])

  const patchMessage = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)))
  }, [])

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
      // 会話が無ければ作成してから送信（履歴として永続化される）
      let convId = conversationId
      if (!convId) {
        convId = (await createConversation()).conversation_id
        setConversationId(convId)
      }
      // 送信するとエージェントジョブが作られる。完了までポーリングし、
      // 進捗フェーズ（意図判定/委任/レポート生成…）を生成中バブルに表示する。
      const { job_id } = await postMessage(convId, text)
      const startedAt = Date.now()
      for (;;) {
        await sleep(POLL_MS)
        const job = await getJob(job_id)
        if (job.status === 'done') {
          patchMessage(pendingId, {
            pending: false,
            phaseText: undefined,
            content: job.result ?? '(回答が空でした)',
          })
          break
        }
        if (job.status === 'error') {
          patchMessage(pendingId, {
            pending: false,
            phaseText: undefined,
            isError: true,
            content: `回答の生成に失敗しました: ${job.error ?? '不明なエラー'}`,
          })
          break
        }
        const current = job.progress?.at(-1)
        if (current) {
          patchMessage(pendingId, {
            phaseText: `${current.label}: ${PHASE_LABELS[current.status]}`,
          })
        }
        if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
          patchMessage(pendingId, {
            pending: false,
            isError: true,
            content: 'タイムアウトしました。もう一度お試しください。',
          })
          break
        }
      }
    } catch (e) {
      patchMessage(pendingId, {
        pending: false,
        isError: true,
        content: `送信に失敗しました: ${e instanceof Error ? e.message : e}`,
      })
    } finally {
      setBusy(false)
    }
  }, [input, busy, conversationId, patchMessage])

  /** 新しい会話を開始する（現在の表示をクリア。次回送信時に会話を作成）。 */
  const newConversation = useCallback(() => {
    setConversationId(null)
    setMessages([])
    setView('chat')
  }, [])

  /** 会話一覧を取得する（q でタイトル検索）。 */
  const loadConversations = useCallback(async (q = '') => {
    setHistoryLoading(true)
    try {
      setConversations(await getConversations(q))
    } catch {
      setConversations([])
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  /** 過去の会話を選択してメッセージを読み込む。 */
  const selectConversation = useCallback(async (id: string) => {
    setBusy(true)
    try {
      const history = await getMessages(id)
      setConversationId(id)
      setMessages(
        history.map((m) => ({
          id: m.message_id,
          role: m.role,
          content: m.content,
        })),
      )
      setView('chat')
    } catch {
      // 取得失敗時は履歴表示のまま
    } finally {
      setBusy(false)
    }
  }, [])

  /** 会話を削除する。表示中の会話なら新規会話状態に戻す。 */
  const removeConversation = useCallback(
    async (id: string) => {
      try {
        await deleteConversation(id)
      } catch {
        return
      }
      setConversations((prev) => prev.filter((c) => c.conversation_id !== id))
      if (conversationId === id) {
        setConversationId(null)
        setMessages([])
      }
    },
    [conversationId],
  )

  return {
    isOpen,
    rect,
    setRect,
    view,
    setView,
    input,
    setInput,
    messages,
    busy,
    conversationId,
    conversations,
    historyLoading,
    open,
    close,
    send,
    newConversation,
    loadConversations,
    selectConversation,
    removeConversation,
  }
}
