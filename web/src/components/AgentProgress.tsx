import { useState } from 'react'
import type { AgentStep, JobStatus } from '../types/api'

// mode=single（旧パイプライン）のステータスマッピング用フォールバック表示
const FALLBACK_AGENTS = [
  '受付・解析',
  'Web情報収集',
  'ニュース分析',
  'EDINET調査',
  'テクニカル分析',
  '財務分析',
  '統合・合成',
  '回答生成',
]

type StepState = 'done' | 'active' | 'waiting' | 'error'

interface DisplayStep {
  key: string
  label: string
  state: StepState
  summary: string | null
}

function fallbackSteps(status: JobStatus): DisplayStep[] {
  const make = (doneCount: number, activeIndex: number): StepState[] =>
    FALLBACK_AGENTS.map((_, i) => {
      if (i < doneCount) return 'done'
      if (i === activeIndex) return 'active'
      return 'waiting'
    })

  let states: StepState[]
  switch (status) {
    case 'pending':
      states = make(0, 0)
      break
    case 'researching_web':
      states = make(1, 1)
      break
    case 'researching_edinet':
      states = make(3, 3)
      break
    case 'synthesizing':
      states = make(5, 5)
      break
    case 'responding':
      states = make(7, 7)
      break
    case 'done':
      states = make(8, -1)
      break
    default:
      states = FALLBACK_AGENTS.map(() => 'waiting')
  }
  return FALLBACK_AGENTS.map((label, i) => ({
    key: label,
    label,
    state: states[i],
    summary: null,
  }))
}

function progressSteps(progress: AgentStep[]): DisplayStep[] {
  return progress.map((step) => ({
    key: step.key,
    label: step.label,
    state:
      step.status === 'running'
        ? 'active'
        : (step.status as StepState),
    summary: step.summary,
  }))
}

function headline(steps: DisplayStep[], status: JobStatus): string {
  if (status === 'error') return 'エラー'
  if (status === 'done') return '完了'
  const active = steps.filter((s) => s.state === 'active')
  if (active.length > 0) {
    return `${active.map((s) => s.label).join('・')}中…`
  }
  return '処理中…'
}

interface Props {
  status: JobStatus
  progress?: AgentStep[]
}

export function AgentProgress({ status, progress }: Props) {
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const steps = progress?.length ? progressSteps(progress) : fallbackSteps(status)
  const selected = steps.find((s) => s.key === selectedKey)
  const isWorking = status !== 'done' && status !== 'error'

  const toggle = (step: DisplayStep) => {
    setSelectedKey((prev) => (prev === step.key ? null : step.key))
  }

  return (
    <div className="agent-progress">
      <div className="agent-progress-label">
        {isWorking && <span className="agent-pulse" />}
        <span>{headline(steps, status)}</span>
      </div>
      <div className="agent-steps">
        {steps.map((step) => (
          <button
            key={step.key}
            type="button"
            className={`agent-step agent-step--${step.state} ${
              selectedKey === step.key ? 'agent-step--selected' : ''
            }`}
            title={step.summary ?? undefined}
            onClick={() => toggle(step)}
          >
            <span className="agent-step-dot">
              {step.state === 'done' && (
                <svg width="8" height="8" viewBox="0 0 10 10" fill="none">
                  <path
                    d="M2 5l2.5 2.5L8 3"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
              {step.state === 'error' && <span className="agent-step-x">✕</span>}
            </span>
            <span className="agent-step-name">{step.label}</span>
          </button>
        ))}
      </div>
      {selected && (
        <div className="agent-step-detail">
          <div className="agent-step-detail-title">{selected.label}</div>
          <div className="agent-step-detail-body">
            {selected.summary ??
              (selected.state === 'active'
                ? '実行中…'
                : selected.state === 'waiting'
                  ? '実行待ち'
                  : '詳細情報はありません')}
          </div>
        </div>
      )}
    </div>
  )
}
