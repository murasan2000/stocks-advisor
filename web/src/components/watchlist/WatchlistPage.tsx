import { Plus } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { MarketSection } from '../common/MarketSection'
import { StockTable } from '../screener/StockTable'
import { StockDetail } from './StockDetail'
import type { StockRow } from '../../types/api'
import { isJpCode } from '../../utils/format'
import { useSortState } from '../../hooks/useSortState'
import { useToggleSet } from '../../hooks/useToggleSet'

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
  // 開いているチャートの銘柄コード集合（複数銘柄を同時に展開できる。
  // 行を再クリックすると畳む＝トグル。閉じるボタンは remove を使う）。
  const openDetails = useToggleSet()
  const { prune: pruneOpenDetails } = openDetails
  // ウォッチ解除等で一覧から消えた銘柄は開閉状態も掃除する（再登録時に
  // 開いたまま復活しないように）。
  useEffect(() => {
    pruneOpenDetails(rows.map((r) => r.code))
  }, [rows, pruneOpenDetails])
  const [showAddForm, setShowAddForm] = useState(false)
  const [addCode, setAddCode] = useState('')
  const [addBusy, setAddBusy] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  // 円建て（日本株）とドル建て（米国株）で通貨が異なるため、表示テーブル・ソート
  // 状態をそれぞれ独立させる（片方の並べ替えがもう片方に影響しないように）。
  const jpRowsRaw = useMemo(() => rows.filter((r) => isJpCode(r.code)), [rows])
  const usRowsRaw = useMemo(() => rows.filter((r) => !isJpCode(r.code)), [rows])
  const jp = useSortState(jpRowsRaw, compare, 'code', false)
  const us = useSortState(usRowsRaw, compare, 'code', false)

  const renderDetail = (code: string) => (
    <StockDetail
      key={code}
      code={code}
      row={rows.find((r) => r.code === code)}
      onClose={() => openDetails.remove(code)}
    />
  )

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
        <>
          <MarketSection label="日本株" count={jp.sorted.length}>
            <StockTable
              stocks={jp.sorted}
              sortBy={jp.sortBy}
              sortDesc={jp.sortDesc}
              onSort={jp.handleSort}
              loading={loading}
              watchedCodes={watchedCodes}
              onToggleWatch={onToggleWatch}
              onRowClick={openDetails.toggle}
              openCodes={openDetails.items}
              renderDetail={renderDetail}
              selected={selected}
              onToggleSelect={onToggleSelect}
            />
          </MarketSection>
          <MarketSection label="米国株" count={us.sorted.length}>
            <StockTable
              stocks={us.sorted}
              sortBy={us.sortBy}
              sortDesc={us.sortDesc}
              onSort={us.handleSort}
              loading={loading}
              watchedCodes={watchedCodes}
              onToggleWatch={onToggleWatch}
              onRowClick={openDetails.toggle}
              openCodes={openDetails.items}
              renderDetail={renderDetail}
              selected={selected}
              onToggleSelect={onToggleSelect}
            />
          </MarketSection>
        </>
      )}
    </main>
  )
}
