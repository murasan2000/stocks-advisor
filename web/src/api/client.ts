import type {
  Conversation,
  ConversationMessage,
  CreateJobResponse,
  Filters,
  FxQuote,
  HistoryPeriod,
  Holding,
  ImportResult,
  Job,
  Label,
  MarketCategoryInfo,
  MarketReport,
  ScreenerMeta,
  SendMessageResponse,
  StockHistory,
  StockRow,
  StocksResponse,
} from '../types/api'

const BASE_URL = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API error ${res.status}: ${body || res.statusText}`)
  }
  return res.json() as Promise<T>
}

function buildQuery(filters: Filters, stage: number): string {
  const p = new URLSearchParams()
  p.set('stage', String(stage))
  if (filters.q.trim()) p.set('q', filters.q.trim())
  for (const m of filters.markets) p.append('markets', m)
  const numeric: [string, number | undefined][] = [
    ['per_min', filters.perMin],
    ['per_max', filters.perMax],
    ['pbr_max', filters.pbrMax],
    ['dividend_yield_min', filters.dividendYieldMin],
    ['roe_min', filters.roeMin],
    ['market_cap_min', filters.marketCapMin],
  ]
  for (const [key, value] of numeric) {
    if (value !== undefined && value !== null) p.set(key, String(value))
  }
  if (filters.oversold) {
    p.set('oversold', 'true')
    p.set('drop_from_high_pct', String(filters.dropFromHighPct))
    p.set('rebound_from_low_pct', String(filters.reboundFromLowPct))
  }
  p.set('sort_by', filters.sortBy)
  p.set('sort_desc', String(filters.sortDesc))
  return p.toString()
}

export function getStocks(filters: Filters, stage: number): Promise<StocksResponse> {
  return request<StocksResponse>(`/screener/stocks?${buildQuery(filters, stage)}`)
}

export function getScreenerMeta(): Promise<ScreenerMeta> {
  return request<ScreenerMeta>('/screener/meta')
}

export function refreshSnapshot(): Promise<CreateJobResponse> {
  return request<CreateJobResponse>('/screener/refresh', { method: 'POST' })
}

export function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}`)
}

// ───────────────────────────────────────────────
// ウォッチリスト
// ───────────────────────────────────────────────

export function getWatchlist(): Promise<StockRow[]> {
  return request<StockRow[]>('/watchlist')
}

export function getWatchlistCodes(): Promise<string[]> {
  return request<string[]>('/watchlist/codes')
}

// 追加/削除はレスポンスボディが空のため request()（.json() 呼び出し）は使わない。
export function addToWatchlist(code: string): Promise<void> {
  return fetch(`${BASE_URL}/watchlist/${encodeURIComponent(code)}`, {
    method: 'POST',
  }).then((res) => {
    if (!res.ok) throw new Error(`API error ${res.status}`)
  })
}

export function removeFromWatchlist(code: string): Promise<void> {
  return fetch(`${BASE_URL}/watchlist/${encodeURIComponent(code)}`, {
    method: 'DELETE',
  }).then((res) => {
    if (!res.ok) throw new Error(`API error ${res.status}`)
  })
}

export function getStockHistory(
  code: string,
  period: HistoryPeriod,
): Promise<StockHistory> {
  return request<StockHistory>(
    `/stocks/${encodeURIComponent(code)}/history?period=${period}`,
  )
}

// ───────────────────────────────────────────────
// ラベル（ウォッチリスト銘柄への自由付与タグ、issue #68）
// ───────────────────────────────────────────────

export function getLabels(): Promise<Label[]> {
  return request<Label[]>('/labels')
}

export function createLabel(name: string): Promise<Label> {
  return request<Label>('/labels', { method: 'POST', body: JSON.stringify({ name }) })
}

// レスポンスボディが空のため request()（.json() 呼び出し）は使わない。
export function deleteLabel(labelId: string): Promise<void> {
  return fetch(`${BASE_URL}/labels/${encodeURIComponent(labelId)}`, {
    method: 'DELETE',
  }).then((res) => {
    if (!res.ok) throw new Error(`API error ${res.status}`)
  })
}

export function attachLabel(code: string, labelId: string): Promise<void> {
  return fetch(
    `${BASE_URL}/watchlist/${encodeURIComponent(code)}/labels/${encodeURIComponent(labelId)}`,
    { method: 'POST' },
  ).then((res) => {
    if (!res.ok) throw new Error(`API error ${res.status}`)
  })
}

export function detachLabel(code: string, labelId: string): Promise<void> {
  return fetch(
    `${BASE_URL}/watchlist/${encodeURIComponent(code)}/labels/${encodeURIComponent(labelId)}`,
    { method: 'DELETE' },
  ).then((res) => {
    if (!res.ok) throw new Error(`API error ${res.status}`)
  })
}

// ───────────────────────────────────────────────
// 保有銘柄（ポートフォリオ）
// ───────────────────────────────────────────────

export function getHoldings(): Promise<Holding[]> {
  return request<Holding[]>('/portfolio/holdings')
}

// レスポンスボディが空のため request()（.json() 呼び出し）は使わない。
export function upsertHolding(
  code: string,
  quantity: number,
  avgCost: number,
): Promise<void> {
  return fetch(`${BASE_URL}/portfolio/holdings/${encodeURIComponent(code)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quantity, avg_cost: avgCost }),
  }).then((res) => {
    if (!res.ok) throw new Error(`API error ${res.status}`)
  })
}

export function removeHolding(code: string): Promise<void> {
  return fetch(`${BASE_URL}/portfolio/holdings/${encodeURIComponent(code)}`, {
    method: 'DELETE',
  }).then((res) => {
    if (!res.ok) throw new Error(`API error ${res.status}`)
  })
}

// multipart/form-data はブラウザが境界(boundary)付きの Content-Type を
// 自動設定する必要があるため、request() のヘッダーは使わず直接 fetch する。
export async function importHoldingsCsv(file: File): Promise<ImportResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${BASE_URL}/portfolio/holdings/import`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API error ${res.status}: ${body || res.statusText}`)
  }
  return res.json() as Promise<ImportResult>
}

// ───────────────────────────────────────────────
// チャット履歴
// ───────────────────────────────────────────────

export function createConversation(): Promise<Conversation> {
  return request<Conversation>('/chat/conversations', { method: 'POST' })
}

export function getConversations(q = '', limit = 30): Promise<Conversation[]> {
  const p = new URLSearchParams({ limit: String(limit) })
  if (q.trim()) p.set('q', q.trim())
  return request<Conversation[]>(`/chat/conversations?${p.toString()}`)
}

export function deleteConversation(conversationId: string): Promise<void> {
  return fetch(`${BASE_URL}/chat/conversations/${conversationId}`, {
    method: 'DELETE',
  }).then((res) => {
    if (!res.ok) throw new Error(`API error ${res.status}`)
  })
}

export function getMessages(
  conversationId: string,
): Promise<ConversationMessage[]> {
  return request<ConversationMessage[]>(
    `/chat/conversations/${conversationId}/messages`,
  )
}

export function postMessage(
  conversationId: string,
  content: string,
  tickers?: string[],
): Promise<SendMessageResponse> {
  return request<SendMessageResponse>(
    `/chat/conversations/${conversationId}/messages`,
    { method: 'POST', body: JSON.stringify({ content, tickers: tickers ?? [] }) },
  )
}

// ───────────────────────────────────────────────
// マーケット情報画面
// ───────────────────────────────────────────────

export function getMarketCategories(): Promise<MarketCategoryInfo[]> {
  return request<MarketCategoryInfo[]>('/market/categories')
}

export function getMarketFx(): Promise<FxQuote[]> {
  return request<FxQuote[]>('/market/fx')
}

// カテゴリを1件指定してレポートJobを作成する（kind=market の汎用エージェントJob）。
export function createMarketReportJob(categoryId: string): Promise<CreateJobResponse> {
  return request<CreateJobResponse>('/jobs', {
    method: 'POST',
    body: JSON.stringify({
      kind: 'market',
      query: 'マーケット情報',
      categories: [categoryId],
    }),
  })
}

// レポートが保存されている日付一覧（新しい順、issue #66）。カレンダーの非活性判定に使う。
export function getMarketReportDates(categoryId: string): Promise<string[]> {
  return request<string[]>(`/market/reports/${encodeURIComponent(categoryId)}/dates`)
}

// 指定日の保存済みレポートを取得する（issue #66。Job不要・即時）。
export function getMarketReport(categoryId: string, date: string): Promise<MarketReport> {
  return request<MarketReport>(
    `/market/reports/${encodeURIComponent(categoryId)}?date=${encodeURIComponent(date)}`,
  )
}
