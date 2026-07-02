import { Send, Sparkles, Trash2, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { ChatRect, useChat } from '../../hooks/useChat'
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
  const { isOpen, close, rect, setRect } = chat

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
            <span>AIアシスタント</span>
          </div>
          <div className="chat-header-actions">
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
              onClick={close}
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
