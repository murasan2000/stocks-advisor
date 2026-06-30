import { AGENT_OPTIONS, type AgentKey } from '../types/api'

interface Props {
  selected: AgentKey[]
  onChange: (selected: AgentKey[]) => void
  disabled: boolean
}

/**
 * ホーム（空状態）でエージェントを大きめのブロックで表示する。
 * ホバーで各エージェントの説明文を表示し、クリックで実行対象として選択できる。
 * 未選択のままなら既定のエージェント（MVP では Market Agent）が実行される。
 */
export function AgentShowcase({ selected, onChange, disabled }: Props) {
  const toggle = (key: AgentKey) => {
    onChange(
      selected.includes(key)
        ? selected.filter((k) => k !== key)
        : [...selected, key],
    )
  }

  return (
    <div className="agent-showcase">
      <div className="agent-showcase-grid">
        {AGENT_OPTIONS.map((agent) => {
          const active = selected.includes(agent.key)
          return (
            <button
              key={agent.key}
              type="button"
              className={`agent-card ${active ? 'agent-card--active' : ''}`}
              onClick={() => toggle(agent.key)}
              disabled={disabled}
              aria-pressed={active}
            >
              <span className="agent-card-label">{agent.label}</span>
              <span className="agent-card-desc">{agent.description}</span>
            </button>
          )
        })}
      </div>
      <p className="agent-showcase-hint">
        {selected.length === 0
          ? 'Market Agent が日本市場の概況を分析します'
          : `${selected.length}個のエージェントを選択中`}
      </p>
    </div>
  )
}
