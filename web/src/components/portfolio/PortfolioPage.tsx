import { Plus, Upload } from 'lucide-react'
import { useMemo, useRef, useState } from 'react'
import type { Holding } from '../../types/api'
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
}: Props) {
  const [sortBy, setSortBy] = useState<SortableKey>('market_value')
  const [sortDesc, setSortDesc] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [addCode, setAddCode] = useState('')
  const [addQuantity, setAddQuantity] = useState('')
  const [addAvgCost, setAddAvgCost] = useState('')
  const [addBusy, setAddBusy] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)
  const [importBusy, setImportBusy] = useState(false)
  const [importMessage, setImportMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const sortedHoldings = useMemo(() => {
    const sorted = [...holdings].sort((a, b) => compare(a, b, sortBy))
    return sortDesc ? sorted.reverse() : sorted
  }, [holdings, sortBy, sortDesc])

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

      <PortfolioSummary holdings={holdings} />

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="portfolio-actions">
        <button
          type="button"
          className="portfolio-action-btn"
          onClick={() => setShowAddForm((v) => !v)}
        >
          <Plus size={15} />
          銘柄を追加
        </button>
        <button
          type="button"
          className="portfolio-action-btn"
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
        <form className="portfolio-add-form" onSubmit={(e) => void handleAddSubmit(e)}>
          <input
            type="text"
            placeholder="銘柄コード（例: 7203）"
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
            placeholder="平均取得単価"
            value={addAvgCost}
            onChange={(e) => setAddAvgCost(e.target.value)}
          />
          <button type="submit" disabled={addBusy}>
            {addBusy ? '追加中…' : '追加'}
          </button>
          {addError ? <span className="portfolio-add-error">{addError}</span> : null}
        </form>
      ) : null}

      {loading ? (
        <div className="loading-bar">
          <span />
        </div>
      ) : null}

      <HoldingsTable
        holdings={sortedHoldings}
        loading={loading}
        sortBy={sortBy}
        sortDesc={sortDesc}
        onSort={handleSort}
        onRemove={(code) => void onRemove(code)}
        watchedCodes={watchedCodes}
        onToggleWatch={onToggleWatch}
        selected={selected}
        onToggleSelect={onToggleSelect}
      />
    </main>
  )
}
