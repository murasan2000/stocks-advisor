import { Plus } from 'lucide-react'
import { useMemo, useState } from 'react'
import { StockTable } from '../screener/StockTable'
import { StockDetail } from './StockDetail'
import type { StockRow } from '../../types/api'

interface Props {
  rows: StockRow[]
  loading: boolean
  watchedCodes: Set<string>
  onToggleWatch: (code: string) => void
  // AI企業分析の対象選択（スクリーニング画面と共通の state をそのまま使う）
  selected: Set<string>
  onToggleSelect: (code: string) => void
  // 銘柄コード直接入力での追加（日本株コード・米国株ティッカーどちらも可）
  onAdd: (code: string) => Promise<void>
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

export function WatchlistPage({
  rows,
  loading,
  watchedCodes,
  onToggleWatch,
  selected,
  onToggleSelect,
  onAdd,
}: Props) {
  const [sortBy, setSortBy] = useState<SortableKey>('code')
  const [sortDesc, setSortDesc] = useState(false)
  const [detailCode, setDetailCode] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [addCode, setAddCode] = useState('')
  const [addBusy, setAddBusy] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

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

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const code = addCode.trim().toUpperCase()
    if (!code) {
      setAddError('銘柄コード（日本株）またはティッカー（米国株）を入力してください')
      return
    }
    setAddBusy(true)
    setAddError(null)
    try {
      await onAdd(code)
      setAddCode('')
      setShowAddForm(false)
    } catch (err) {
      setAddError(err instanceof Error ? err.message : String(err))
    } finally {
      setAddBusy(false)
    }
  }

  return (
    <main className="screener-main">
      <header className="screener-header-title">
        <h1>ウォッチリスト</h1>
        <p>登録した銘柄の一覧です。銘柄をクリックすると詳細を表示します。</p>
      </header>

      <div className="page-actions">
        <button
          type="button"
          className="page-action-btn"
          onClick={() => setShowAddForm((v) => !v)}
          // 送信中にフォームを閉じるとエラー表示ごと消えてしまうため、閉じられないようにする
          disabled={addBusy}
        >
          <Plus size={15} />
          銘柄を追加
        </button>
      </div>

      {showAddForm ? (
        <form className="inline-add-form" onSubmit={(e) => void handleAddSubmit(e)}>
          <input
            type="text"
            placeholder="銘柄コード（例: 7203）またはティッカー（例: AAPL）"
            value={addCode}
            onChange={(e) => setAddCode(e.target.value)}
          />
          <button type="submit" disabled={addBusy}>
            {addBusy ? '追加中…' : '追加'}
          </button>
          {addError ? <span className="inline-add-error">{addError}</span> : null}
        </form>
      ) : null}

      {loading ? (
        <div className="loading-bar">
          <span />
        </div>
      ) : null}

      {!loading && rows.length === 0 ? (
        <div className="table-empty watchlist-empty">
          まだウォッチリストに銘柄が登録されていません。
          <br />
          スクリーニング画面の★マーク、または上の「銘柄を追加」から登録してください
          （米国株は上のフォームからティッカーを直接入力してください）。
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
          selected={selected}
          onToggleSelect={onToggleSelect}
        />
      )}

      {detailCode ? (
        <StockDetail
          // 別銘柄への切り替え時に前の銘柄のチャート/統計が一瞬残らないよう、
          // key を変えて確実に再マウント（内部 state をリセット）する。
          key={detailCode}
          code={detailCode}
          row={rows.find((r) => r.code === detailCode)}
          onClose={() => setDetailCode(null)}
        />
      ) : null}
    </main>
  )
}
