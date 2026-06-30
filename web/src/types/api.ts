export const JOB_STATUSES = [
  'pending',
  'researching_web',
  'researching_edinet',
  'synthesizing',
  'responding',
  'running',
  'done',
  'error',
] as const

export type JobStatus = (typeof JOB_STATUSES)[number]

/** 選択可能なエージェント（バックエンドの AGENT_SEQUENCE と一致させる）
 *
 * MVP では Market Agent（日本株）のみ。今後 Company / Financial / Technical /
 * News / Recommendation などを Issue ごとに追加していく。
 */
export const AGENT_OPTIONS = [
  {
    key: 'market',
    label: '市場分析',
    description:
      '日経平均・TOPIX・ドル円から日本市場全体の概況（リスクオン/オフ）を★評価付きで要約します。',
  },
] as const

export type AgentKey = (typeof AGENT_OPTIONS)[number]['key']

export type AgentStepStatus = 'waiting' | 'running' | 'done' | 'error'

/** マルチエージェント実行の1ステップ分の進捗（mode=multi のみ） */
export interface AgentStep {
  key: string
  label: string
  status: AgentStepStatus
  summary: string | null
  started_at: number | null
  finished_at: number | null
}

export interface Job {
  job_id: string
  query: string
  status: JobStatus
  result: string | null
  error: string | null
  progress: AgentStep[] | null
  created_at: number
  updated_at: number
}

export interface CreateJobResponse {
  job_id: string
  status: JobStatus
}

/** 市場サマリーの指数・為替・金利 1 項目（GET /market/overview） */
export interface IndexQuote {
  symbol: string
  name: string
  category: 'index' | 'fx' | 'rate' | 'volatility'
  price: number
  change_pct: number
}

/** Market Agent の出力（市場全体の概況） */
export interface MarketOverview {
  indices: IndexQuote[]
  market_trend: string
  macro_score: number
  rating: number
  as_of: string
  summary: string
}

export const STATUS_LABELS: Record<JobStatus, string> = {
  pending: '受付中…',
  researching_web: 'Webから情報収集中…',
  researching_edinet: '開示情報を調査中…',
  synthesizing: '分析結果を統合中…',
  responding: '回答を生成中…',
  running: 'マルチエージェント分析中…',
  done: '完了',
  error: 'エラー',
}
