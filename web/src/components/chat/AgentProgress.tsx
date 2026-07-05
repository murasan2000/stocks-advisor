import { Check, CircleDashed, Loader2, X } from 'lucide-react'
import { type AgentStep, PHASE_LABELS } from '../../types/api'

/** 実行中ジョブの進捗ステップを一覧表示する（Phase 8: Job状態の可視化）。 */
export function AgentProgress({ steps }: { steps: AgentStep[] }) {
  return (
    <ul className="agent-progress" aria-label="実行状況">
      {steps.map((step) => {
        const state =
          step.status === 'done'
            ? 'done'
            : step.status === 'error'
              ? 'error'
              : step.status === 'waiting'
                ? 'waiting'
                : 'running'
        return (
          <li key={step.key} className={`agent-step agent-step--${state}`}>
            <span className="agent-step-icon">
              {state === 'done' ? (
                <Check size={13} />
              ) : state === 'error' ? (
                <X size={13} />
              ) : state === 'waiting' ? (
                <CircleDashed size={13} />
              ) : (
                <Loader2 size={13} className="spinning" />
              )}
            </span>
            <span className="agent-step-label">{step.label}</span>
            <span className="agent-step-status">{PHASE_LABELS[step.status]}</span>
            {step.summary ? (
              <span className="agent-step-summary" title={step.summary}>
                {step.summary}
              </span>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}
