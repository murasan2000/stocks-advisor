import { ArrowDown, ArrowUp } from 'lucide-react'
import type { StockRow } from '../../types/api'
import {
  fmtMarketCap,
  fmtNum,
  fmtPct,
  fmtPrice,
  fmtVolume,
} from '../../utils/format'

interface Column {
  key: string
  label: string
  sortable: boolean
  align?: 'right'
}

const COLUMNS: Column[] = [
  { key: 'code', label: 'コード', sortable: true },
  { key: 'name', label: '銘柄名', sortable: false },
  { key: 'price', label: '株価', sortable: true, align: 'right' },
  { key: 'change_pct', label: '前日比', sortable: true, align: 'right' },
  { key: 'volume', label: '出来高', sortable: true, align: 'right' },
  { key: 'market_cap', label: '時価総額', sortable: true, align: 'right' },
  { key: 'per', label: 'PER', sortable: true, align: 'right' },
  { key: 'pbr', label: 'PBR', sortable: true, align: 'right' },
  { key: 'dividend_yield', label: '配当', sortable: true, align: 'right' },
  { key: 'roe', label: 'ROE', sortable: true, align: 'right' },
  { key: 'rsi', label: 'RSI', sortable: true, align: 'right' },
  { key: 'score', label: 'スコア', sortable: true, align: 'right' },
]

interface Props {
  stocks: StockRow[]
  sortBy: string
  sortDesc: boolean
  onSort: (key: string) => void
  loading: boolean
}

function scoreColor(score: number): string {
  if (score >= 70) return 'var(--success)'
  if (score >= 45) return 'var(--accent-3)'
  return 'var(--text-dim)'
}

export function StockTable({ stocks, sortBy, sortDesc, onSort, loading }: Props) {
  return (
    <div className="table-wrap">
      <table className="stock-table">
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th
                key={c.key}
                className={`${c.align === 'right' ? 'right' : ''} ${
                  c.sortable ? 'sortable' : ''
                }`}
                onClick={c.sortable ? () => onSort(c.key) : undefined}
              >
                <span>{c.label}</span>
                {c.sortable && sortBy === c.key ? (
                  sortDesc ? (
                    <ArrowDown size={12} />
                  ) : (
                    <ArrowUp size={12} />
                  )
                ) : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {stocks.map((s) => {
            const up = (s.change_pct ?? 0) >= 0
            return (
              <tr key={s.code}>
                <td className="code">{s.code}</td>
                <td>
                  <div className="name-cell">
                    <span className="name">{s.name}</span>
                    <span className="market-tag">{s.market}</span>
                  </div>
                </td>
                <td className="right strong">{fmtPrice(s.price)}</td>
                <td className={`right ${up ? 'up' : 'down'}`}>
                  {fmtPct(s.change_pct)}
                </td>
                <td className="right dim">{fmtVolume(s.volume)}</td>
                <td className="right dim">{fmtMarketCap(s.market_cap)}</td>
                <td className="right">{fmtNum(s.per, 1)}</td>
                <td className="right">{fmtNum(s.pbr, 2)}</td>
                <td className="right">
                  {s.dividend_yield === null ? '—' : `${s.dividend_yield.toFixed(2)}%`}
                </td>
                <td className="right">
                  {s.roe === null ? '—' : `${s.roe.toFixed(1)}%`}
                </td>
                <td className="right">{fmtNum(s.rsi, 0)}</td>
                <td className="right">
                  <div className="score-cell">
                    <div className="score-bar">
                      <span
                        style={{
                          width: `${s.score}%`,
                          background: scoreColor(s.score),
                        }}
                      />
                    </div>
                    <span className="score-num">{s.score}</span>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {!loading && stocks.length === 0 ? (
        <div className="table-empty">条件に一致する銘柄がありません</div>
      ) : null}
    </div>
  )
}
