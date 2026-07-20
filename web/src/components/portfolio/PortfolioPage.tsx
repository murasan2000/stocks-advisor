import { Plus, Upload } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import type { Holding, StockRow } from '../../types/api'
import { MarketSection } from '../common/MarketSection'
import { isJpCode } from '../../utils/format'
import { useSortState } from '../../hooks/useSortState'
import { StockDetail } from '../watchlist/StockDetail'
import { HoldingsTable } from './HoldingsTable'
import { PortfolioSummary } from './PortfolioSummary'

type SortableKey = Exclude<keyof Holding, 'symbol' | 'name' | 'market'>

function compare(a: Holding, b: Holding, key: SortableKey): number {
  if (key === 'code') {
    const diff = (Number(a.code.replace(/\D/g, '')) || 0) - (Number(b.code.replace(/\D/g, '')) || 0)
    return diff !== 0 ? diff : a.code.localeCompare(b.code)
  }
  const av = a[key]
  const bv = b[key]
  const an = av === null ? Number.NEGATIVE_INFINITY : Number(av)
  const bn = bv === null ? Number.NEGATIVE_INFINITY : Number(bv)
  return an - bn
}

interface Props {
  holdings: Holding[]
  loading: boolean
  error: string | null
  onAdd: (code: string, quantity: number, avgCost: number) => Promise<void>
  onRemove: (code: string) => Promise<void>
  onImportCsv: (file: File) => Promise<{ imported: number }>
  watchedCodes: Set<string>
  onToggleWatch: (code: string) => void
  selected: Set<string>
  onToggleSelect: (code: string) => void
  // 詳細パネルの時価総額/PER/PBR等はスクリーナー由来のスナップショットを流用する
  stocks: StockRow[]
}

export function PortfolioPage({
  holdings,
  loading,
  error,
  onAdd,
  onRemove,
  onImportCsv,
  watchedCodes,
  onToggleWatch,
  selected,
  onToggleSelect,
  stocks,
}: Props) {
  const [detailCode, setDetailCode] = useState<string | null>(null)
  const [showAddForm, setShowAddForm] = useState(false)
  const [addCode, setAddCode] = useState('')
  const [addQuantity, setAddQuantity] = useState('')
  const [addAvgCost, setAddAvgCost] = useState('')
  const [addBusy, setAddBusy] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const [importBusy, setImportBusy] = useState(false)
  const [importMessage, setImportMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // 円建て（日本株）とドル建て（米国株）で通貨が異なるため、表示テーブル・合計・
  // ソート状態をそれぞれ独立させる（片方の並べ替えがもう片方に影響しないように）。
  const jpHoldingsRaw = useMemo(() => holdings.filter((h) => isJpCode(h.code)), [holdings])
  const usHoldingsRaw = useMemo(() => holdings.filter((h) => !isJpCode(h.code)), [holdings])
  const jp = useSortState(jpHoldingsRaw, compare, 'market_value', true)
  const us = useSortState(usHoldingsRaw, compare, 'market_value', true)

  const detailHolding = useMemo(
    () => holdings.find((h) => h.code === detailCode),
    [holdings, detailCode],
  )
  // stocks はスクリーナーの検索/絞り込み状態に依存するため、保有銘柄がその条件から
  // 外れていても表示できるよう、見つからない場合は Holding 自身の情報で最低限を補う。
  const detailRow: StockRow | undefined = useMemo(() => {
    const fromScreener = stocks.find((r) => r.code === detailCode)
    if (fromScreener) return fromScreener
    if (!detailHolding) return undefined
    return {
      code: detailHolding.code,
      symbol: detailHolding.symbol,
      name: detailHolding.name,
      market: detailHolding.market,
      price: detailHolding.price,
      change_pct: null,
      volume: null,
      market_cap: null,
      per: null,
      pbr: null,
      dividend_yield: null,
      roe: null,
      rsi: null,
      high_5y: null,
      low_1y: null,
      drop_from_high_pct: null,
      rebound_from_low_pct: null,
      score: 0,
    }
  }, [stocks, detailCode, detailHolding])

  const handleRemove = (code: string) => {
    void onRemove(code)
    // 詳細パネルを開いたまま削除した場合、存在しない銘柄のパネルが残らないよう閉じる
    if (code === detailCode) setDetailCode(null)
  }

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const quantity = Number(addQuantity)
    const avgCost = Number(addAvgCost)
    if (!addCode.trim() || !(quantity > 0) || !(avgCost > 0)) {
      setAddError('銘柄コード・数量・平均取得単価を正しく入力してください')
      return
    }
    setAddBusy(true)
    setAddError(null)
    try {
      await onAdd(addCode.trim(), quantity, avgCost)
      setAddCode('')
      setAddQuantity('')
      setAddAvgCost('')
      setShowAddForm(false)
    } catch (e) {
      setAddError(e instanceof Error ? e.message : String(e))
    } finally {
      setAddBusy(false)
    }
  }

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = '' // 同じファイルを連続選択しても onChange が発火するように
    if (!file) return
    setImportBusy(true)
    setImportMessage(null)
    try {
      const result = await onImportCsv(file)
      setImportMessage(`${result.imported} 銘柄を取り込みました`)
    } catch (err) {
      setImportMessage(
        `インポートに失敗しました: ${err instanceof Error ? err.message : String(err)}`,
      )
    } finally {
      setImportBusy(false)
    }
  }

  return (
    <main className="screener-main">
      <header className="screener-header-title">
        <h1>保有銘柄</h1>
        <p>実際に保有している銘柄の含み損益・資産配分を確認できます。</p>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

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
        <button
          type="button"
          className="page-action-btn"
          onClick={() => fileInputRef.current?.click()}
          disabled={importBusy}
        >
          <Upload size={15} />
          {importBusy ? 'インポート中…' : 'CSVインポート（楽天証券）'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => void handleFileChange(e)}
        />
      </div>

      {importMessage ? <p className="portfolio-import-message">{importMessage}</p> : null}

      {showAddForm ? (
        <form className="inline-add-form" onSubmit={(e) => void handleAddSubmit(e)}>
          <input
            type="text"
            placeholder="銘柄コード（例: 7203）またはティッカー（例: AAPL）"
            value={addCode}
            onChange={(e) => setAddCode(e.target.value)}
          />
          <input
            type="number"
            placeholder="保有数量"
            value={addQuantity}
            onChange={(e) => setAddQuantity(e.target.value)}
          />
          <input
            type="number"
            placeholder="平均取得単価（日本株は円、米国株はドル）"
            value={addAvgCost}
            onChange={(e) => setAddAvgCost(e.target.value)}
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

      {!loading && holdings.length === 0 ? (
        <div className="table-empty">保有銘柄が登録されていません</div>
      ) : (
        <>
          {/* 円建て/ドル建てを合算した単一の総資産額は表示しない（為替レートが
              必要になり、CSVインポートの通貨モデルをドル建てのまま保つ方針
              [issue #62] と矛盾するため）。合計は通貨ごとに独立して表示する。 */}
          <MarketSection label="日本株" count={jp.sorted.length}>
            <PortfolioSummary holdings={jp.sorted} currency="JPY" />
            <HoldingsTable
              holdings={jp.sorted}
              sortBy={jp.sortBy}
              sortDesc={jp.sortDesc}
              onSort={jp.handleSort}
              onRemove={handleRemove}
              watchedCodes={watchedCodes}
              onToggleWatch={onToggleWatch}
              selected={selected}
              onToggleSelect={onToggleSelect}
              onRowClick={setDetailCode}
            />
          </MarketSection>
          <MarketSection label="米国株" count={us.sorted.length}>
            <PortfolioSummary holdings={us.sorted} currency="USD" />
            <HoldingsTable
              holdings={us.sorted}
              sortBy={us.sortBy}
              sortDesc={us.sortDesc}
              onSort={us.handleSort}
              onRemove={handleRemove}
              watchedCodes={watchedCodes}
              onToggleWatch={onToggleWatch}
              selected={selected}
              onToggleSelect={onToggleSelect}
              onRowClick={setDetailCode}
            />
          </MarketSection>
        </>
      )}

      {detailCode ? (
        <StockDetail
          // 別銘柄への切り替え時に前の銘柄のチャート/統計が残らないよう再マウントする
          key={detailCode}
          code={detailCode}
          row={detailRow}
          onClose={() => setDetailCode(null)}
          holding={
            detailHolding
              ? {
                  quantity: detailHolding.quantity,
                  avgCost: detailHolding.avg_cost,
                  marketValue: detailHolding.market_value,
                  pnl: detailHolding.pnl,
                  pnlPct: detailHolding.pnl_pct,
                }
              : undefined
          }
        />
      ) : null}
    </main>
  )
}
