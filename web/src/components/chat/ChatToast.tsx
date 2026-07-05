import { CheckCircle2, XCircle } from 'lucide-react'
import { useEffect } from 'react'
import type { ChatNotice } from '../../hooks/useChat'

const AUTO_DISMISS_MS = 8000

interface Props {
  notice: ChatNotice
  onOpen: () => void
  onDismiss: () => void
}

/** モーダルを閉じて待っている間にジョブが完了/失敗したときのトースト通知。 */
export function ChatToast({ notice, onOpen, onDismiss }: Props) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, AUTO_DISMISS_MS)
    return () => clearTimeout(timer)
  }, [onDismiss])

  return (
    <button
      type="button"
      className={`chat-toast chat-toast--${notice.type}`}
      onClick={onOpen}
    >
      {notice.type === 'done' ? (
        <CheckCircle2 size={17} />
      ) : (
        <XCircle size={17} />
      )}
      <span>{notice.text}</span>
      <span className="chat-toast-hint">クリックで表示</span>
    </button>
  )
}
