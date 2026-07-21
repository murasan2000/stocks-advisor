import { X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getStockHistory } from '../../api/client'
import {
  HISTORY_PERIODS,
  type Candle,
  type HistoryPeriod,
  type StockRow,
} from '../../types/api'
import {
  fmtMarketCapByCode,
  fmtNum,
  fmtPct,
  fmtPriceByCode,
  fmtVolume,
} from '../../utils/format'
import { CandlestickChart } from './CandlestickChart'

// ポートフォリオ画面から渡す保有銘柄の統計（保有していない場合は undefined）
export interface HoldingStats {
  quantity: number
  avgCost: number
  marketValue: number | null
  pnl: number | null
  pnlPct: number | null
}

interface Props {
  code: string
  row: StockRow | undefined
  onClose: () => void
  holding?: HoldingStats
}

const DEFAULT_PERIOD: HistoryPeriod = '1y'

export function StockDetail({ code, row, onClose, holding }: Props) {
  const [period, setPeriod] = useState<HistoryPeriod>(DEFAULT_PERIOD)
  const [candles, setCandles] = useState<Candle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    // setState をエフェクト本体で同期的に呼ばないよう、取得処理をマクロタスクへずらす
    // （useScreener の debounce と同じ手法）。
    const timer = setTimeout(() => {
      setLoading(true)
      setError(null)
      getStockHistory(code, period)
        .then((data) => {
          if (!cancelled) setCandles(data.candles)
        })
        .catch((e: unknown) => {
          if (!cancelled) setError(e instanceof Error ? e.message : String(e))
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, 0)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [code, period])

  const latest = candles.at(-1)
  const prevClose = candles.at(-2)?.close
  const changePct =
    latest && prevClose ? ((latest.close - prevClose) / prevClose) * 100 : null
  const pnlClass = holding && (holding.pnl ?? 0) >= 0 ? 'up' : 'down'

  return (
    <section className="stock-detail">
      <header className="stock-detail-header">
        <div className="stock-detail-title">
          <h2>{row?.name ?? code}</h2>
          <span className="code">{code}</span>
          {row?.market ? <span className="market-tag">{row.market}</span> : null}
        </div>
        <button type="button" className="stock-detail-close" onClick={onClose}>
          <X size={16} />
          閉じる
        </button>
      </header>

      <div className="stock-detail-period-tabs">
        {HISTORY_PERIODS.map((p) => (
          <button
            key={p.key}
            type="button"
            className={p.key === period ? 'active' : ''}
            onClick={() => setPeriod(p.key)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-bar">
          <span />
        </div>
      ) : null}
      {error ? <div className="error-banner">{error}</div> : null}
      {!loading && !error && candles.length > 0 ? (
        <CandlestickChart candles={candles} code={code} avgCost={holding?.avgCost} />
      ) : null}
      {!loading && !error && candles.length === 0 ? (
        <div className="table-empty">チャートデータを取得できませんでした</div>
      ) : null}

      <div className="stock-detail-stats">
        {holding ? (
          <>
            <div className="detail-stat">
              <span className="detail-stat-label">保有数量</span>
              <span className="detail-stat-value">{fmtNum(holding.quantity, 0)}</span>
            </div>
            <div className="detail-stat">
              <span className="detail-stat-label">取得単価</span>
              <span className="detail-stat-value">
                {fmtPriceByCode(code, holding.avgCost)}
              </span>
            </div>
            <div className="detail-stat">
              <span className="detail-stat-label">評価額</span>
              <span className="detail-stat-value strong">
                {fmtPriceByCode(code, holding.marketValue)}
              </span>
            </div>
            <div className="detail-stat">
              <span className="detail-stat-label">評価損益</span>
              <span className={`detail-stat-value ${pnlClass}`}>
                {fmtPriceByCode(code, holding.pnl)}
              </span>
            </div>
            <div className="detail-stat">
              <span className="detail-stat-label">評価損益率</span>
              <span className={`detail-stat-value ${pnlClass}`}>{fmtPct(holding.pnlPct)}</span>
            </div>
          </>
        ) : null}
        <div className="detail-stat">
          <span className="detail-stat-label">現在値</span>
          <span className="detail-stat-value strong">
            {fmtPriceByCode(code, latest?.close ?? row?.price ?? null)}
          </span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">前日比</span>
          <span className={`detail-stat-value ${(changePct ?? 0) >= 0 ? 'up' : 'down'}`}>
            {fmtPct(changePct ?? row?.change_pct ?? null)}
          </span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">当日高値</span>
          <span className="detail-stat-value">
            {fmtPriceByCode(code, latest?.high ?? null)}
          </span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">当日安値</span>
          <span className="detail-stat-value">
            {fmtPriceByCode(code, latest?.low ?? null)}
          </span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">出来高</span>
          <span className="detail-stat-value">{fmtVolume(latest?.volume ?? null)}</span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">時価総額</span>
          <span className="detail-stat-value">
            {fmtMarketCapByCode(code, row?.market_cap ?? null)}
          </span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">PER</span>
          <span className="detail-stat-value">{fmtNum(row?.per ?? null, 1)}</span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">PBR</span>
          <span className="detail-stat-value">{fmtNum(row?.pbr ?? null, 2)}</span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">配当利回り</span>
          <span className="detail-stat-value">
            {row?.dividend_yield == null ? '—' : `${row.dividend_yield.toFixed(2)}%`}
          </span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">ROE</span>
          <span className="detail-stat-value">
            {row?.roe == null ? '—' : `${row.roe.toFixed(1)}%`}
          </span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">5年高値</span>
          <span className="detail-stat-value">
            {fmtPriceByCode(code, row?.high_5y ?? null)}
          </span>
        </div>
        <div className="detail-stat">
          <span className="detail-stat-label">1年安値</span>
          <span className="detail-stat-value">
            {fmtPriceByCode(code, row?.low_1y ?? null)}
          </span>
        </div>
      </div>
    </section>
  )
}
