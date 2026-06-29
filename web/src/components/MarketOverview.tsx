import { RefreshCw } from 'lucide-react'
import { useMarketOverview } from '../hooks/useMarketOverview'
import type { IndexQuote } from '../types/api'

function formatPrice(q: IndexQuote): string {
  if (q.category === 'fx') return `${q.price.toFixed(2)}円`
  if (q.category === 'rate') return `${q.price.toFixed(3)}%`
  return q.price.toLocaleString('ja-JP', { maximumFractionDigits: 2 })
}

function Stars({ rating }: { rating: number }) {
  const r = Math.max(0, Math.min(5, rating))
  return (
    <span className="market-rating" aria-label={`総合評価 ${r} / 5`}>
      {'★'.repeat(r)}
      {'☆'.repeat(5 - r)}
    </span>
  )
}

export function MarketOverview() {
  const { overview, loading, error, refresh } = useMarketOverview()

  return (
    <section className="panel-card">
      <div className="market-header">
        <h3 className="panel-section-title">市場概況</h3>
        <button
          type="button"
          className="market-refresh"
          onClick={refresh}
          disabled={loading}
          aria-label="更新"
        >
          <RefreshCw size={14} className={loading ? 'spinning' : ''} />
        </button>
      </div>

      {overview ? (
        <>
          <div className="market-summary-head">
            <Stars rating={overview.rating} />
            <span className="market-trend-badge">{overview.market_trend}</span>
          </div>

          <div className="market-list">
            {overview.indices.map((m) => {
              const up = m.change_pct >= 0
              return (
                <div key={m.symbol} className="market-item">
                  <span className="market-item-name">{m.name}</span>
                  <div className="market-item-right">
                    <span className="market-item-value">{formatPrice(m)}</span>
                    <span className={`market-item-change ${up ? 'up' : 'down'}`}>
                      {up ? '+' : ''}
                      {m.change_pct.toFixed(2)}%
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
          <p className="market-asof">{overview.as_of} 時点</p>
        </>
      ) : loading ? (
        <p className="market-disclaimer">読み込み中…</p>
      ) : error ? (
        <p className="market-disclaimer">市場データを取得できませんでした</p>
      ) : null}
    </section>
  )
}
