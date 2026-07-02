import { ArrowLeft, History, Send, Sparkles, SquarePen, Trash2, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { ChatRect, useChat } from '../../hooks/useChat'
import { fmtTimestamp } from '../../utils/format'
import { ChatMessage } from './ChatMessage'

type ChatState = ReturnType<typeof useChat>

const MIN_W = 320
const MIN_H = 380
const MARGIN = 8
const MOBILE_BREAKPOINT = 700 // これ未満は全画面表示（ドラッグ/リサイズ無効）

/** move=ヘッダードラッグ移動 / それ以外=辺・角のリサイズ（n=上, s=下, e=右, w=左） */
type DragMode = 'move' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

const RESIZE_HANDLES: DragMode[] = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

/**
 * 右下アンカー（x=右, y=下オフセット）の矩形にドラッグ/リサイズを適用する。
 * 左/上辺は反対側の辺を固定したまま、右/下辺はアンカーごと追従して伸縮する。
 */
function applyDrag(
  mode: DragMode,
  start: ChatRect,
  dx: number,
  dy: number,
  vw: number,
  vh: number,
): ChatRect {
  let { w, h, x, y } = start
  if (mode === 'move') {
    x = clamp(start.x - dx, MARGIN, Math.max(MARGIN, vw - start.w - MARGIN))
    y = clamp(start.y - dy, MARGIN, Math.max(MARGIN, vh - start.h - MARGIN))
    return { w, h, x, y }
  }
  if (mode.includes('w')) {
    w = clamp(start.w - dx, MIN_W, vw - start.x - MARGIN)
  }
  if (mode.includes('e')) {
    const d = clamp(dx, MIN_W - start.w, start.x - MARGIN)
    w = start.w + d
    x = start.x - d
  }
  if (mode.includes('n')) {
    h = clamp(start.h - dy, MIN_H, vh - start.y - MARGIN)
  }
  if (mode.includes('s')) {
    const d = clamp(dy, MIN_H - start.h, start.y - MARGIN)
    h = start.h + d
    y = start.y - d
  }
  return { w, h, x, y }
}

export function ChatModal({ chat }: { chat: ChatState }) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<{
    mode: DragMode
    startX: number
    startY: number
    rect: ChatRect
  } | null>(null)
  const [historyQuery, setHistoryQuery] = useState('')
  const { isOpen, close, rect, setRect, view, setView, loadConversations } = chat

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.messages])

  // Escape キーで閉じる（外側クリックと同じ挙動）
  useEffect(() => {
    if (!isOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [isOpen, close])

  // 履歴ビューを開いたとき・検索語変更時に会話一覧を取得（入力はデバウンス）
  useEffect(() => {
    if (!isOpen || view !== 'history') return
    const timer = setTimeout(() => {
      void loadConversations(historyQuery)
    }, 200)
    return () => clearTimeout(timer)
  }, [isOpen, view, historyQuery, loadConversations])

  if (!isOpen) return null

  const startDrag = (e: React.PointerEvent<HTMLElement>) => {
    const mode = e.currentTarget.dataset.dragMode as DragMode | undefined
    if (!mode) return
    if (window.innerWidth < MOBILE_BREAKPOINT) return // モバイルは全画面固定
    // ヘッダー上のボタン類はドラッグ対象にしない
    if (mode === 'move' && (e.target as HTMLElement).closest('button')) return
    dragRef.current = { mode, startX: e.clientX, startY: e.clientY, rect }
    e.currentTarget.setPointerCapture(e.pointerId)
    e.preventDefault()
  }

  const onDragMove = (e: React.PointerEvent<HTMLElement>) => {
    const d = dragRef.current
    if (!d) return
    setRect(
      applyDrag(
        d.mode,
        d.rect,
        e.clientX - d.startX,
        e.clientY - d.startY,
        window.innerWidth,
        window.innerHeight,
      ),
    )
  }

  const endDrag = () => {
    dragRef.current = null
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      // IME 変換確定の Enter では送信しない（keyCode 229 は Safari 対策）
      if (e.nativeEvent.isComposing || e.keyCode === 229) return
      e.preventDefault()
      void chat.send()
    }
  }

  return (
    <div
      className="chat-overlay"
      role="dialog"
      aria-label="AIアシスタント"
      // モーダル外クリックで閉じる（×ボタンと同じ挙動）
      onPointerDown={(e) => {
        if (e.target === e.currentTarget) close()
      }}
    >
      <div
        className="chat-modal"
        style={{ width: rect.w, height: rect.h, right: rect.x, bottom: rect.y }}
      >
        {RESIZE_HANDLES.map((mode) => (
          <div
            key={mode}
            className={`chat-resize chat-resize--${mode}`}
            data-drag-mode={mode}
            onPointerDown={startDrag}
            onPointerMove={onDragMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
          />
        ))}

        <header
          className="chat-header"
          data-drag-mode="move"
          onPointerDown={startDrag}
          onPointerMove={onDragMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          <div className="chat-title">
            <Sparkles size={16} />
            <span>{view === 'history' ? 'チャット履歴' : 'AIアシスタント'}</span>
          </div>
          <div className="chat-header-actions">
            {view === 'chat' ? (
              <>
                <button
                  type="button"
                  className="chat-icon-btn"
                  onClick={chat.newConversation}
                  disabled={chat.messages.length === 0}
                  aria-label="新しい会話"
                  title="新しい会話"
                >
                  <SquarePen size={16} />
                </button>
                <button
                  type="button"
                  className="chat-icon-btn"
                  onClick={() => setView('history')}
                  aria-label="チャット履歴"
                  title="チャット履歴"
                >
                  <History size={16} />
                </button>
              </>
            ) : (
              <button
                type="button"
                className="chat-icon-btn"
                onClick={() => setView('chat')}
                aria-label="チャットに戻る"
                title="チャットに戻る"
              >
                <ArrowLeft size={16} />
              </button>
            )}
            <button
              type="button"
              className="chat-icon-btn"
              onClick={close}
              aria-label="閉じる"
              title="閉じる"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        {view === 'history' ? (
          <div className="chat-history">
            <input
              type="text"
              className="chat-history-search"
              placeholder="会話を検索"
              value={historyQuery}
              onChange={(e) => setHistoryQuery(e.target.value)}
            />
            <div className="chat-history-list">
              {chat.historyLoading ? (
                <p className="chat-history-empty">読み込み中…</p>
              ) : chat.conversations.length === 0 ? (
                <p className="chat-history-empty">
                  {historyQuery ? '一致する会話がありません' : '履歴はありません'}
                </p>
              ) : (
                chat.conversations.map((c) => (
                  <div
                    key={c.conversation_id}
                    className={`chat-conv-item ${
                      c.conversation_id === chat.conversationId
                        ? 'chat-conv-item--active'
                        : ''
                    }`}
                  >
                    <button
                      type="button"
                      className="chat-conv-main"
                      onClick={() => void chat.selectConversation(c.conversation_id)}
                    >
                      <span className="chat-conv-title">
                        {c.title || '（無題の会話）'}
                      </span>
                      <span className="chat-conv-time">
                        {fmtTimestamp(c.updated_at)}
                      </span>
                    </button>
                    <button
                      type="button"
                      className="chat-icon-btn"
                      onClick={() => void chat.removeConversation(c.conversation_id)}
                      aria-label="この会話を削除"
                      title="この会話を削除"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        ) : (
          <>
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
          </>
        )}
      </div>
    </div>
  )
}
