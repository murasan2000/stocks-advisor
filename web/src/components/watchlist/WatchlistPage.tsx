import { useMemo, useState } from 'react'
import { StockTable } from '../screener/StockTable'
import type { StockRow } from '../../types/api'

interface Props {
  rows: StockRow[]
  loading: boolean
  watchedCodes: Set<string>
  onToggleWatch: (code: string) => void
}

// StockRow の中でソート対象になり得るキーのみ（比較可能な値を持つもの）
type SortableKey = Exclude<keyof StockRow, 'symbol' | 'name' | 'market'>

function compare(a: StockRow, b: StockRow, key: SortableKey): number {
  if (key === 'code') {
    // 数字部分で比較しつつ、"167A"/"167B" のような英字違いは文字列比較で決着させる
    const diff = (Number(a.code.replace(/\D/g, '')) || 0) - (Number(b.code.replace(/\D/g, '')) || 0)
    return diff !== 0 ? diff : a.code.localeCompare(b.code)
  }
  const av = a[key]
  const bv = b[key]
  const an = av === null ? Number.NEGATIVE_INFINITY : Number(av)
  const bn = bv === null ? Number.NEGATIVE_INFINITY : Number(bv)
  return an - bn
}

export function WatchlistPage({ rows, loading, watchedCodes, onToggleWatch }: Props) {
  const [sortBy, setSortBy] = useState<SortableKey>('code')
  const [sortDesc, setSortDesc] = useState(false)
  // 銘柄詳細チャート画面は Phase 3 で実装。それまではプレースホルダーを表示する。
  const [detailCode, setDetailCode] = useState<string | null>(null)

  const sortedRows = useMemo(() => {
    const sorted = [...rows].sort((a, b) => compare(a, b, sortBy))
    return sortDesc ? sorted.reverse() : sorted
  }, [rows, sortBy, sortDesc])

  const handleSort = (key: string) => {
    if (key === sortBy) {
      setSortDesc((d) => !d)
    } else {
      setSortBy(key as SortableKey)
      setSortDesc(true)
    }
  }

  return (
    <main className="screener-main">
      <header className="screener-header-title">
        <h1>ウォッチリスト</h1>
        <p>登録した銘柄の一覧です。銘柄をクリックすると詳細を表示します。</p>
      </header>

      {loading ? (
        <div className="loading-bar">
          <span />
        </div>
      ) : null}

      {!loading && rows.length === 0 ? (
        <div className="table-empty watchlist-empty">
          まだウォッチリストに銘柄が登録されていません。
          <br />
          スクリーニング画面の★マークから追加してください。
        </div>
      ) : (
        <StockTable
          stocks={sortedRows}
          sortBy={sortBy}
          sortDesc={sortDesc}
          onSort={handleSort}
          loading={loading}
          watchedCodes={watchedCodes}
          onToggleWatch={onToggleWatch}
          onRowClick={setDetailCode}
        />
      )}

      {detailCode ? (
        <div className="watchlist-detail-placeholder">
          <span>{detailCode} の詳細チャートは近日公開予定です</span>
          <button type="button" onClick={() => setDetailCode(null)}>
            閉じる
          </button>
        </div>
      ) : null}
    </main>
  )
}
