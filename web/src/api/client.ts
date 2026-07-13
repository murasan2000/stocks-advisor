import type {
  Conversation,
  ConversationMessage,
  CreateJobResponse,
  Filters,
  HistoryPeriod,
  Holding,
  ImportResult,
  Job,
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
): Promise<SendMessageResponse> {
  return request<SendMessageResponse>(
    `/chat/conversations/${conversationId}/messages`,
    { method: 'POST', body: JSON.stringify({ content }) },
  )
}
