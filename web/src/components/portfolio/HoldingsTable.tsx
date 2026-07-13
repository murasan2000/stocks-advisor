import { ArrowDown, ArrowUp, Star, Trash2 } from 'lucide-react'
import type { Holding } from '../../types/api'
import { fmtNum, fmtPct, fmtPrice } from '../../utils/format'

interface Column {
  key: string
  label: string
  align?: 'right'
  sortable?: boolean
}

// 銘柄名は文字列のため数値ソート対象外（PortfolioPage の SortableKey も除外している）
const COLUMNS: Column[] = [
  { key: 'code', label: 'コード', sortable: true },
  { key: 'name', label: '銘柄名', sortable: false },
  { key: 'quantity', label: '保有数量', align: 'right', sortable: true },
  { key: 'avg_cost', label: '平均取得単価', align: 'right', sortable: true },
  { key: 'price', label: '現在値', align: 'right', sortable: true },
  { key: 'market_value', label: '評価額', align: 'right', sortable: true },
  { key: 'pnl', label: '評価損益', align: 'right', sortable: true },
  { key: 'pnl_pct', label: '評価損益率', align: 'right', sortable: true },
]

interface Props {
  holdings: Holding[]
  loading: boolean
  sortBy: string
  sortDesc: boolean
  onSort: (key: string) => void
  onRemove: (code: string) => void
  watchedCodes: Set<string>
  onToggleWatch: (code: string) => void
  // 銘柄選択（AI企業分析）はスクリーニング/ウォッチリストと共通の任意機能
  selected?: Set<string>
  onToggleSelect?: (code: string) => void
  onRowClick?: (code: string) => void
}

export function HoldingsTable({
  holdings,
  loading,
  sortBy,
  sortDesc,
  onSort,
  onRemove,
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
            <th className="select-col" />
          </tr>
        </thead>
        <tbody>
          {holdings.map((h) => {
            const up = (h.pnl ?? 0) >= 0
            const isSelected = selected?.has(h.code) ?? false
            const isWatched = watchedCodes.has(h.code)
            return (
              <tr
                key={h.code}
                className={`${isSelected ? 'row--selected' : ''} ${
                  onRowClick ? 'row--clickable' : ''
                }`}
                onClick={onRowClick ? () => onRowClick(h.code) : undefined}
              >
                {showSelectCol ? (
                  <td className="select-col" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => onToggleSelect?.(h.code)}
                      aria-label={`${h.name} を分析対象に選択`}
                    />
                  </td>
                ) : null}
                <td className="watch-col" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className={`watch-star ${isWatched ? 'watch-star--active' : ''}`}
                    onClick={() => onToggleWatch(h.code)}
                    aria-label={
                      isWatched
                        ? `${h.name} をウォッチリストから解除`
                        : `${h.name} をウォッチリストに追加`
                    }
                    title={isWatched ? 'ウォッチリストから解除' : 'ウォッチリストに追加'}
                  >
                    <Star size={15} fill={isWatched ? 'currentColor' : 'none'} />
                  </button>
                </td>
                <td className="code">{h.code}</td>
                <td>
                  <div className="name-cell">
                    <span className="name">{h.name}</span>
                    {h.market ? <span className="market-tag">{h.market}</span> : null}
                  </div>
                </td>
                <td className="right">{fmtNum(h.quantity, 0)}</td>
                <td className="right dim">{fmtPrice(h.avg_cost)}</td>
                <td className="right strong">{fmtPrice(h.price)}</td>
                <td className="right">{fmtPrice(h.market_value)}</td>
                <td className={`right ${up ? 'up' : 'down'}`}>{fmtPrice(h.pnl)}</td>
                <td className={`right ${up ? 'up' : 'down'}`}>{fmtPct(h.pnl_pct)}</td>
                <td className="select-col" onClick={(e) => e.stopPropagation()}>
                  <button
                    type="button"
                    className="holding-remove"
                    onClick={() => onRemove(h.code)}
                    aria-label={`${h.name} を削除`}
                    title="削除"
                  >
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {!loading && holdings.length === 0 ? (
        <div className="table-empty">保有銘柄が登録されていません</div>
      ) : null}
    </div>
  )
}
