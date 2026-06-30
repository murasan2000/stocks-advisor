import { AGENT_OPTIONS, type AgentKey } from '../types/api'

interface Props {
  selected: AgentKey[]
  onChange: (selected: AgentKey[]) => void
  disabled: boolean
}

/**
 * 実行するエージェントを選択する。MVP では Market Agent（市場分析）のみ。
 * 未選択（空）の場合は既定のエージェントを実行する。
 * 今後エージェントを追加すると、ここに自動で並ぶ。
 */
export function AgentSelector({ selected, onChange, disabled }: Props) {
  const toggle = (key: AgentKey) => {
    onChange(
      selected.includes(key)
        ? selected.filter((k) => k !== key)
        : [...selected, key],
    )
  }

  const allSelected = selected.length === 0

  return (
    <div className="agent-selector">
      <div className="agent-selector-head">
        <span className="agent-selector-title">実行するエージェント</span>
        <button
          type="button"
          className="agent-selector-all"
          onClick={() => onChange([])}
          disabled={disabled || allSelected}
        >
          すべて実行
        </button>
      </div>
      <div className="agent-selector-chips">
        {AGENT_OPTIONS.map((agent) => {
          const active = selected.includes(agent.key)
          return (
            <button
              key={agent.key}
              type="button"
              className={`agent-chip ${active ? 'agent-chip--active' : ''}`}
              onClick={() => toggle(agent.key)}
              disabled={disabled}
              aria-pressed={active}
            >
              {agent.label}
            </button>
          )
        })}
      </div>
      <p className="agent-selector-hint">
        {allSelected
          ? '未選択のため既定のエージェントを実行します'
          : '選択したエージェントを実行します'}
      </p>
    </div>
  )
}
