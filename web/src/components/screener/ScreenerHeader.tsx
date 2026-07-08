import { Activity, RefreshCw, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { ScreenerMeta } from '../../types/api'
import { fmtTimestamp } from '../../utils/format'

// 検索テキストは入力の都度リクエストせず、この時間だけ待ってから反映する。
const SEARCH_DEBOUNCE_MS = 600

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
  // 入力中はローカル state で即時表示し、一定時間後に onSearch へ反映する。
  const [text, setText] = useState(q)
  // 外部（クリアなど）から q が変わったらローカル入力にも同期する。
  // 描画中に前回値と比較して合わせる（effect 内 setState を避ける公式パターン）。
  const [prevQ, setPrevQ] = useState(q)
  if (q !== prevQ) {
    setPrevQ(q)
    setText(q)
  }

  // 入力が落ち着いたら検索を実行（不要な連続リクエストを防ぐ）。
  useEffect(() => {
    if (text === q) return
    const timer = setTimeout(() => onSearch(text), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [text, q, onSearch])
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
            value={text}
            onChange={(e) => setText(e.target.value)}
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
