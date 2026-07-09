import { ArrowDown, ArrowUp, Star } from 'lucide-react'
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
  watchedCodes: Set<string>
  onToggleWatch: (code: string) => void
  // 銘柄選択（AI企業分析）はスクリーニング画面のみで使う任意機能
  selected?: Set<string>
  onToggleSelect?: (code: string) => void
  // 行クリックで詳細を開く（ウォッチリスト画面のみで使用）
  onRowClick?: (code: string) => void
}

function scoreColor(score: number): string {
  if (score >= 70) return 'var(--success)'
  if (score >= 45) return 'var(--accent-3)'
  return 'var(--text-dim)'
}

export function StockTable({
  stocks,
  sortBy,
  sortDesc,
  onSort,
  loading,
  watchedCodes,
  onToggleWatch,
  selected,
  onToggleSelect,
  onRowClick,
}: Props) {
  const showSelectCol = onToggleSelect != null

  return (
    <div className="table-wrap">
      <table className="stock-table">
        <thead>
          <tr>
            {showSelectCol ? (
              <th className="select-col" title="選択して企業分析に利用">
                分析
              </th>
            ) : null}
            <th className="watch-col" title="ウォッチリスト" />
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
            const isSelected = selected?.has(s.code) ?? false
            const isWatched = watchedCodes.has(s.code)
            return (
              <tr
                key={s.code}
                className={`${isSelected ? 'row--selected' : ''} ${
                  onRowClick ? 'row--clickable' : ''
                }`}
                onClick={onRowClick ? () => onRowClick(s.code) : undefined}
              >
                {showSelectCol ? (
                  <td className="select-col" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => onToggleSelect?.(s.code)}
                      aria-label={`${s.name} を分析対象に選択`}
                    />
                  </td>
                ) : null}
                <td className="watch-col" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className={`watch-star ${isWatched ? 'watch-star--active' : ''}`}
                    onClick={() => onToggleWatch(s.code)}
                    aria-label={
                      isWatched
                        ? `${s.name} をウォッチリストから解除`
                        : `${s.name} をウォッチリストに追加`
                    }
                    title={isWatched ? 'ウォッチリストから解除' : 'ウォッチリストに追加'}
                  >
                    <Star size={15} fill={isWatched ? 'currentColor' : 'none'} />
                  </button>
                </td>
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
