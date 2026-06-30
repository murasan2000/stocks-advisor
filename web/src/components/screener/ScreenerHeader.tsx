import { Activity, RefreshCw, Search } from 'lucide-react'
import type { ScreenerMeta } from '../../types/api'
import { fmtTimestamp } from '../../utils/format'

interface Props {
  meta: ScreenerMeta | null
  total: number
  q: string
  onSearch: (value: string) => void
  refreshing: boolean
  onRefresh: () => void
}

export function ScreenerHeader({
  meta,
  total,
  q,
  onSearch,
  refreshing,
  onRefresh,
}: Props) {
  const isLive = meta?.source === 'live'
  return (
    <header className="screener-header">
      <div className="screener-header-title">
        <h1>株式スクリーニング</h1>
        <p>PER・PBR・配当・ROE・下がりすぎ反発などの条件で銘柄を絞り込みます</p>
        <div className="screener-meta-line">
          <span className={`source-badge ${isLive ? 'source-badge--live' : ''}`}>
            <Activity size={12} />
            {isLive ? 'リアルデータ Yahoo Finance' : 'モックデータ'}
          </span>
          <span>
            最終更新: {fmtTimestamp(meta?.last_refresh ?? null)}
          </span>
          <span className="screener-count">
            {total.toLocaleString('ja-JP')} / {(meta?.snapshot_count ?? 0).toLocaleString('ja-JP')} 銘柄
          </span>
        </div>
      </div>

      <div className="screener-header-actions">
        <div className="search-box">
          <Search size={15} />
          <input
            type="text"
            placeholder="銘柄コード・名前で検索"
            value={q}
            onChange={(e) => onSearch(e.target.value)}
          />
        </div>
        <button
          type="button"
          className="refresh-btn"
          onClick={onRefresh}
          disabled={refreshing}
        >
          <RefreshCw size={15} className={refreshing ? 'spinning' : ''} />
          {refreshing ? '更新中…' : '更新'}
        </button>
      </div>
    </header>
  )
}
