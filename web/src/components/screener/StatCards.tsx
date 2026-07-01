import { Coins, Filter, Percent, TrendingUp } from 'lucide-react'
import type { ScreenerSummary } from '../../types/api'
import { fmtNum } from '../../utils/format'

interface Props {
  summary: ScreenerSummary | null
}

export function StatCards({ summary }: Props) {
  const s = summary
  const cards = [
    {
      icon: <Filter size={18} />,
      label: '検索結果',
      value: s ? s.count.toLocaleString('ja-JP') : '—',
      unit: '件',
      tone: 'indigo',
    },
    {
      icon: <TrendingUp size={18} />,
      label: '平均PER',
      value: s ? fmtNum(s.avg_per, 1) : '—',
      unit: '倍',
      tone: 'violet',
    },
    {
      icon: <Coins size={18} />,
      label: '平均配当利回り',
      value: s ? fmtNum(s.avg_dividend_yield, 2) : '—',
      unit: '%',
      tone: 'cyan',
    },
    {
      icon: <Percent size={18} />,
      label: '平均ROE',
      value: s ? fmtNum(s.avg_roe, 1) : '—',
      unit: '%',
      tone: 'green',
    },
  ]

  const up = s?.up ?? 0
  const down = s?.down ?? 0
  const unchanged = s?.unchanged ?? 0
  const totalDir = Math.max(up + down + unchanged, 1)

  return (
    <div className="stat-section">
      <div className="stat-cards">
        {cards.map((c) => (
          <div key={c.label} className={`stat-card stat-card--${c.tone}`}>
            <div className="stat-card-icon">{c.icon}</div>
            <div className="stat-card-body">
              <div className="stat-card-value">
                {c.value}
                <span className="stat-card-unit">{c.unit}</span>
              </div>
              <div className="stat-card-label">{c.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="direction-bar-wrap">
        <div className="direction-legend">
          <span className="up">▲ {up} 上昇</span>
          <span className="down">▼ {down} 下落</span>
          <span className="flat">— {unchanged} 変わらず</span>
        </div>
        <div className="direction-bar">
          <span className="seg up" style={{ width: `${(up / totalDir) * 100}%` }} />
          <span className="seg down" style={{ width: `${(down / totalDir) * 100}%` }} />
          <span
            className="seg flat"
            style={{ width: `${(unchanged / totalDir) * 100}%` }}
          />
        </div>
      </div>
    </div>
  )
}
