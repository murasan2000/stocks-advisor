import { useCallback, useRef, useState } from 'react'
import {
  createConversation,
  deleteConversation,
  getConversations,
  getJob,
  getMessages,
  postMessage,
} from '../api/client'
import type { AgentStep, Conversation } from '../types/api'

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
  progress?: AgentStep[] // 生成中の進捗ステップ（Phase 8: 可視化）
}

/** モーダルを閉じている間にジョブが終わったときの通知（トースト表示用）。 */
export interface ChatNotice {
  type: 'done' | 'error'
  text: string
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
  const busyRef = useRef(false) // 外部トリガー（銘柄選択→分析）との二重送信防止
  const [notice, setNotice] = useState<ChatNotice | null>(null)
  const isOpenRef = useRef(false) // ポーリング完了時に「閉じたまま待ったか」を判定
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  const open = useCallback(() => {
    setIsOpen(true)
    isOpenRef.current = true
    setNotice(null) // 開いたら通知は不要
  }, [])
  const close = useCallback(() => {
    setIsOpen(false)
    isOpenRef.current = false
  }, [])

  /** ジョブ完了/失敗時、モーダルが閉じていればトースト通知を出す。 */
  const notifyIfClosed = useCallback((type: ChatNotice['type']) => {
    if (isOpenRef.current) return
    setNotice(
      type === 'done'
        ? { type, text: 'AIの回答が完了しました' }
        : { type, text: 'AIの回答生成に失敗しました' },
    )
  }, [])

  const patchMessage = useCallback((id: string, patch: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)))
  }, [])

  const sendText = useCallback(async (
    rawText: string,
    opts?: { newConversation?: boolean; tickers?: string[] },
  ) => {
    const text = rawText.trim()
    if (!text || busyRef.current) return
    const pendingId = uid()
    const newMessages: ChatMessage[] = [
      { id: uid(), role: 'user', content: text },
      { id: pendingId, role: 'assistant', content: '', pending: true },
    ]
    if (opts?.newConversation) {
      // 新規チャットルームとして開始（表示中の会話を引き継がない）
      setConversationId(null)
      setMessages(newMessages)
    } else {
      setMessages((prev) => [...prev, ...newMessages])
    }
    setInput('')
    setBusy(true)
    busyRef.current = true
    try {
      // 会話が無ければ作成してから送信（履歴として永続化される）
      let convId = opts?.newConversation ? null : conversationId
      if (!convId) {
        convId = (await createConversation()).conversation_id
        setConversationId(convId)
      }
      // 送信するとエージェントジョブが作られる。完了までポーリングし、
      // 進捗フェーズ（意図判定/委任/レポート生成…）を生成中バブルに表示する。
      const { job_id } = await postMessage(convId, text, opts?.tickers)
      const startedAt = Date.now()
      for (;;) {
        await sleep(POLL_MS)
        const job = await getJob(job_id)
        if (job.status === 'done') {
          patchMessage(pendingId, {
            pending: false,
            progress: undefined,
            content: job.result ?? '(回答が空でした)',
          })
          notifyIfClosed('done')
          break
        }
        if (job.status === 'error') {
          patchMessage(pendingId, {
            pending: false,
            progress: job.progress ?? undefined, // どのステップで失敗したかを残す
            isError: true,
            content: `回答の生成に失敗しました: ${job.error ?? '不明なエラー'}`,
          })
          notifyIfClosed('error')
          break
        }
        if (job.progress?.length) {
          patchMessage(pendingId, { progress: job.progress })
        }
        if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
          patchMessage(pendingId, {
            pending: false,
            isError: true,
            content: 'タイムアウトしました。もう一度お試しください。',
          })
          notifyIfClosed('error')
          break
        }
      }
    } catch (e) {
      patchMessage(pendingId, {
        pending: false,
        isError: true,
        content: `送信に失敗しました: ${e instanceof Error ? e.message : e}`,
      })
      notifyIfClosed('error') // 閉じて待っている場合も失敗に気付けるように
    } finally {
      setBusy(false)
      busyRef.current = false
    }
  }, [conversationId, patchMessage, notifyIfClosed])

  /** 入力欄の内容を送信する。 */
  const send = useCallback(async () => {
    await sendText(input)
  }, [input, sendText])

  /** 選択銘柄の企業分析を依頼する（新規会話でモーダルを開いて自動送信）。 */
  const analyzeTickers = useCallback(
    async (codes: string[]) => {
      if (codes.length === 0) return
      setView('chat')
      open()
      // tickers を明示的に渡すことで、テキストからの銘柄抽出（日本株コード限定の
      // 正規表現）に依存せず、米国株ティッカーも確実に対象として認識させる。
      await sendText(`${codes.join(' ')} を分析してください`, {
        newConversation: true,
        tickers: codes,
      })
    },
    [open, sendText],
  )

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

  const clearNotice = useCallback(() => setNotice(null), [])

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
    notice,
    clearNotice,
    conversationId,
    conversations,
    historyLoading,
    open,
    close,
    send,
    analyzeTickers,
    newConversation,
    loadConversations,
    selectConversation,
    removeConversation,
  }
}
