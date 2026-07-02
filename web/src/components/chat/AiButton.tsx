import { Sparkles } from 'lucide-react'

interface Props {
  onClick: () => void
  hidden?: boolean
}

/** どの画面からでも呼び出せる共通の AI ボタン（フローティング配置）。 */
export function AiButton({ onClick, hidden }: Props) {
  if (hidden) return null
  return (
    <button
      type="button"
      className="ai-button"
      onClick={onClick}
      aria-label="AIアシスタントを開く"
      title="AIアシスタント"
    >
      <Sparkles size={20} />
      <span>AIに聞く</span>
    </button>
  )
}
