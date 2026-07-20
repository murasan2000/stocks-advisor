import { Coins, PieChart, TrendingDown, TrendingUp, Wallet } from 'lucide-react'
import { useMemo } from 'react'
import type { Holding } from '../../types/api'
import { fmtPct, fmtPrice, fmtPriceUsd } from '../../utils/format'

interface Props {
  holdings: Holding[]
  currency: 'JPY' | 'USD'
}

const MARKET_COLORS: Record<string, string> = {
  プライム: 'var(--accent-1)',
  スタンダード: 'var(--accent-3)',
  グロース: 'var(--accent-2)',
}
const UNKNOWN_MARKET_COLOR = 'var(--text-muted)'

export function PortfolioSummary({ holdings, currency }: Props) {
  const fmt = currency === 'JPY' ? fmtPrice : fmtPriceUsd

  const stats = useMemo(() => {
    const totalCost = holdings.reduce((sum, h) => sum + h.cost_value, 0)
    const totalMarketValue = holdings.reduce(
      (sum, h) => sum + (h.market_value ?? h.cost_value),
      0,
    )
    const totalPnl = totalMarketValue - totalCost
    const totalPnlPct = totalCost ? (totalPnl / totalCost) * 100 : null

    // 市場区分（プライム/スタンダード等）の内訳は日本株にのみ意味を持つため、
    // 円建てセクションでのみ算出する。
    const byMarket = new Map<string, number>()
    if (currency === 'JPY') {
      for (const h of holdings) {
        const key = h.market || '不明'
        const value = h.market_value ?? h.cost_value
        byMarket.set(key, (byMarket.get(key) ?? 0) + value)
      }
    }
    const allocation = [...byMarket.entries()]
      .map(([market, value]) => ({
        market,
        value,
        pct: totalMarketValue ? (value / totalMarketValue) * 100 : 0,
      }))
      .sort((a, b) => b.value - a.value)

    return { totalCost, totalMarketValue, totalPnl, totalPnlPct, allocation }
  }, [holdings, currency])

  const up = stats.totalPnl >= 0

  return (
    <div className="stat-section">
      <div className="stat-cards">
        <div className="stat-card stat-card--indigo">
          <div className="stat-card-icon">
            <Wallet size={18} />
          </div>
          <div className="stat-card-body">
            <div className="stat-card-value">{fmt(stats.totalMarketValue)}</div>
            <div className="stat-card-label">総資産額</div>
          </div>
        </div>
        <div className="stat-card stat-card--violet">
          <div className="stat-card-icon">
            <Coins size={18} />
          </div>
          <div className="stat-card-body">
            <div className="stat-card-value">{fmt(stats.totalCost)}</div>
            <div className="stat-card-label">取得総額</div>
          </div>
        </div>
        <div className={`stat-card stat-card--${up ? 'green' : 'red'}`}>
          <div className="stat-card-icon">
            {up ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
          </div>
          <div className="stat-card-body">
            <div className={`stat-card-value ${up ? 'up' : 'down'}`}>
              {fmt(stats.totalPnl)}
            </div>
            <div className="stat-card-label">評価損益</div>
          </div>
        </div>
        <div className="stat-card stat-card--cyan">
          <div className="stat-card-icon">
            <PieChart size={18} />
          </div>
          <div className="stat-card-body">
            <div className={`stat-card-value ${up ? 'up' : 'down'}`}>
              {fmtPct(stats.totalPnlPct)}
            </div>
            <div className="stat-card-label">評価損益率</div>
          </div>
        </div>
      </div>

      {stats.allocation.length > 0 ? (
        <div className="direction-bar-wrap">
          <div className="direction-legend">
            {stats.allocation.map((a) => (
              <span key={a.market}>
                <span
                  className="allocation-dot"
                  style={{
                    background: MARKET_COLORS[a.market] ?? UNKNOWN_MARKET_COLOR,
                  }}
                />
                {a.market} {a.pct.toFixed(0)}%
              </span>
            ))}
          </div>
          <div className="direction-bar">
            {stats.allocation.map((a) => (
              <span
                key={a.market}
                className="seg"
                style={{
                  width: `${a.pct}%`,
                  background: MARKET_COLORS[a.market] ?? UNKNOWN_MARKET_COLOR,
                }}
              />
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
