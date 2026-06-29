import { Zap } from 'lucide-react'

const QUICK_ACTIONS = [
  'トヨタ自動車の今後の見通しは？',
  '日経平均のトレンドを教えて',
  'ソニーの決算分析をして',
  '半導体セクターの動向は？',
]

interface Props {
  onSelect: (query: string) => void
  disabled: boolean
}

export function QuickActions({ onSelect, disabled }: Props) {
  return (
    <section className="panel-card">
      <h3 className="panel-section-title">
        <Zap size={13} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
        クイックアクション
      </h3>
      <div className="quick-actions-list">
        {QUICK_ACTIONS.map((q) => (
          <button
            key={q}
            className="quick-action-btn"
            onClick={() => onSelect(q)}
            disabled={disabled}
          >
            {q}
          </button>
        ))}
      </div>
    </section>
  )
}
