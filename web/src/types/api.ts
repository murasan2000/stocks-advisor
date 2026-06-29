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

/** 選択可能なエージェント（バックエンドの AGENT_SEQUENCE と一致させる） */
export const AGENT_OPTIONS = [
  {
    key: 'portfolio',
    label: 'ポートフォリオ分析',
    description: '楽天証券CSVから保有銘柄・評価損益を読み取ります。',
  },
  {
    key: 'market',
    label: '市場分析',
    description:
      '日経平均・TOPIX・S&P500・NASDAQ・NYダウ・VIX・ドル円・米金利から市場全体の概況（リスクオン/オフ）を★評価付きで要約します。',
  },
  {
    key: 'screening',
    label: '銘柄スクリーニング',
    description: 'クエリと保有銘柄から分析対象の銘柄を抽出します。',
  },
  {
    key: 'market_data',
    label: '市場データ収集',
    description: '対象銘柄の株価・チャート・企業情報を並列で取得します。',
  },
  {
    key: 'technical',
    label: 'テクニカル分析',
    description: '移動平均・RSI・MACD・クロス検出からシグナルを判定します。',
  },
  {
    key: 'fundamental',
    label: '財務分析',
    description: 'EDINETの財務サマリーからバリュエーションを評価します。',
  },
  {
    key: 'risk',
    label: 'リスク評価',
    description: 'ボラティリティ・ドローダウン・集中度などのリスクを評価します。',
  },
  {
    key: 'suggestion',
    label: '投資判断・提案',
    description: '全エージェントの結果をLLMで統合し最終レポートを生成します。',
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
