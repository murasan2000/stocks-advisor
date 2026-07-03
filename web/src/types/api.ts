// ───────────────────────────────────────────────
// ジョブ（スナップショット更新の進捗ポーリング用）
// ───────────────────────────────────────────────

export type JobStatus = 'pending' | 'running' | 'done' | 'error'

/** エージェント実行ステップのフェーズ（バックエンド AgentPhase と一致） */
export type AgentPhase =
  | 'waiting'
  | 'running'
  | 'delegating'
  | 'searching'
  | 'generating_report'
  | 'done'
  | 'error'

/** フェーズ -> 表示ラベル（進捗UIで使用予定 / Phase 8） */
export const PHASE_LABELS: Record<AgentPhase, string> = {
  waiting: '待機中',
  running: '実行中',
  delegating: '委任中',
  searching: '情報収集中',
  generating_report: 'レポート生成中',
  done: '完了',
  error: 'エラー',
}

export interface AgentStep {
  key: string
  label: string
  status: AgentPhase
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
  completed_at: number | null
}

export interface CreateJobResponse {
  job_id: string
  status: JobStatus
}

// ───────────────────────────────────────────────
// チャット履歴
// ───────────────────────────────────────────────

export interface Conversation {
  conversation_id: string
  title: string
  created_at: number
  updated_at: number
}

export interface ConversationMessage {
  message_id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  created_at: number
}

export interface SendMessageResponse {
  conversation: Conversation
  user_message: ConversationMessage
  job_id: string
}

// ───────────────────────────────────────────────
// スクリーナー
// ───────────────────────────────────────────────

export interface StockRow {
  code: string
  symbol: string
  name: string
  market: string
  price: number | null
  change_pct: number | null
  volume: number | null
  market_cap: number | null
  per: number | null
  pbr: number | null
  dividend_yield: number | null
  roe: number | null
  rsi: number | null
  high_5y: number | null
  low_1y: number | null
  drop_from_high_pct: number | null
  rebound_from_low_pct: number | null
  score: number
}

export interface ScreenerSummary {
  count: number
  avg_per: number | null
  avg_dividend_yield: number | null
  avg_roe: number | null
  up: number
  down: number
  unchanged: number
}

export interface ScreenerMeta {
  last_refresh: number | null
  universe_count: number
  snapshot_count: number
  source: string
}

export interface StocksResponse {
  stocks: StockRow[]
  stage: number
  next_stage: number | null
  total: number
  summary: ScreenerSummary
  meta: ScreenerMeta
}

/** 絞り込み条件（クライアント状態）。未設定（undefined / 空）は無効。 */
export interface Filters {
  q: string
  markets: string[]
  perMin?: number
  perMax?: number
  pbrMax?: number
  dividendYieldMin?: number
  roeMin?: number
  marketCapMin?: number
  oversold: boolean
  dropFromHighPct: number
  reboundFromLowPct: number
  sortBy: string
  sortDesc: boolean
}

export const EMPTY_FILTERS: Filters = {
  q: '',
  markets: [],
  oversold: false,
  dropFromHighPct: 50,
  reboundFromLowPct: 10,
  sortBy: 'score',
  sortDesc: true,
}

export const MARKET_OPTIONS = ['プライム', 'スタンダード', 'グロース'] as const

export interface Preset {
  key: string
  label: string
  description: string
  apply: (f: Filters) => Filters
}

/** クイック絞り込みプリセット（サイドの条件をまとめてセット）。 */
export const PRESETS: Preset[] = [
  {
    key: 'value',
    label: '割安株',
    description: 'PER15倍以下・PBR1.5倍以下',
    apply: (f) => ({ ...f, perMax: 15, pbrMax: 1.5 }),
  },
  {
    key: 'dividend',
    label: '高配当',
    description: '配当利回り3.5%以上',
    apply: (f) => ({ ...f, dividendYieldMin: 3.5 }),
  },
  {
    key: 'largecap',
    label: '大型株',
    description: '時価総額1兆円以上',
    apply: (f) => ({ ...f, marketCapMin: 1_000_000_000_000 }),
  },
  {
    key: 'oversold',
    label: '下がりすぎ反発',
    description: '5年高値から50%下落＋直近10%反発',
    apply: (f) => ({
      ...f,
      oversold: true,
      dropFromHighPct: 50,
      reboundFromLowPct: 10,
    }),
  },
  {
    key: 'quality',
    label: '高ROE',
    description: 'ROE15%以上',
    apply: (f) => ({ ...f, roeMin: 15 }),
  },
  {
    key: 'bargain',
    label: 'バーゲン',
    description: '割安＋高配当の複合',
    apply: (f) => ({ ...f, perMax: 12, pbrMax: 1.0, dividendYieldMin: 3 }),
  },
]
