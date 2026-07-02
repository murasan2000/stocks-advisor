import { useCallback, useState } from 'react'
import {
  createConversation,
  deleteConversation,
  getConversations,
  getMessages,
  postMessage,
} from '../api/client'
import type { Conversation } from '../types/api'

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
}

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
      const res = await postMessage(convId, text)
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? { ...m, pending: false, content: res.assistant_message.content }
            : m,
        ),
      )
    } catch (e) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === pendingId
            ? {
                ...m,
                pending: false,
                isError: true,
                content: `送信に失敗しました: ${e instanceof Error ? e.message : e}`,
              }
            : m,
        ),
      )
    } finally {
      setBusy(false)
    }
  }, [input, busy, conversationId])

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
