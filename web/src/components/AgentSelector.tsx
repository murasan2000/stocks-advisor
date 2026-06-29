import { AGENT_OPTIONS, type AgentKey } from '../types/api'

interface Props {
  selected: AgentKey[]
  onChange: (selected: AgentKey[]) => void
  disabled: boolean
}

/**
 * Phase 3.5: 実行するエージェントを複数選択する。
 * 未選択（空）の場合はフルパイプライン（全エージェント）を実行する。
 * 前提エージェントはバックエンドが自動補完するため、ここでは選択のみを扱う。
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
          ? '未選択のため全エージェント（フルパイプライン）を実行します'
          : '選択したエージェントに必要な前提は自動で補完されます'}
      </p>
    </div>
  )
}
