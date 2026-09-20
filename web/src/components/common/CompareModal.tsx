import { X } from 'lucide-react'
import { useEffect } from 'react'
import type { StockRow } from '../../types/api'
import {
  fmtNum,
  fmtPct,
  fmtPriceByCode,
} from '../../utils/format'

interface Props {
  rows: StockRow[]
  onClose: () => void
}

/** 比較テーブルの1行分の定義（Issue #82: 生データの単純比較のみ、LLM評価は含めない）。 */
interface MetricRow {
  label: string
  render: (row: StockRow) => string
  align?: 'right'
}

const METRICS: MetricRow[] = [
  { label: '株価', render: (r) => fmtPriceByCode(r.code, r.price), align: 'right' },
  { label: '前日比', render: (r) => fmtPct(r.change_pct), align: 'right' },
  { label: 'PER', render: (r) => fmtNum(r.per, 1), align: 'right' },
  { label: 'PBR', render: (r) => fmtNum(r.pbr, 2), align: 'right' },
  {
    label: '配当利回り',
    render: (r) => (r.dividend_yield === null ? '—' : `${r.dividend_yield.toFixed(2)}%`),
    align: 'right',
  },
  {
    label: 'ROE',
    render: (r) => (r.roe === null ? '—' : `${r.roe.toFixed(1)}%`),
    align: 'right',
  },
  { label: 'RSI', render: (r) => fmtNum(r.rsi, 0), align: 'right' },
  { label: '総合スコア', render: (r) => String(r.score), align: 'right' },
  { label: '5年高値からの下落率', render: (r) => fmtPct(r.drop_from_high_pct), align: 'right' },
  { label: '1年安値からの反発率', render: (r) => fmtPct(r.rebound_from_low_pct), align: 'right' },
]

/** スクリーナー・ウォッチリストの両方から使う複数銘柄の指標比較モーダル（Issue #82）。
 * LabelPicker と同じ導線（背景クリック・Escapeで閉じる）を踏襲する。
 * 表示は StockRow の既存フィールドをそのまま並べるだけで、LLMによる評価は含めない。 */
export function CompareModal({ rows, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="compare-overlay"
      role="dialog"
      aria-label="銘柄比較"
      onPointerDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="compare-modal">
        <div className="compare-header">
          <span className="compare-title">銘柄比較</span>
          <button
            type="button"
            className="icon-btn"
            onClick={onClose}
            aria-label="閉じる"
            title="閉じる"
          >
            <X size={14} />
          </button>
        </div>

        <div className="table-wrap compare-table-wrap">
          <table className="stock-table compare-table">
            <thead>
              <tr>
                <th>指標</th>
                {rows.map((r) => (
                  <th key={r.code}>
                    <div className="compare-col-head">
                      <span className="name">{r.name}</span>
                      <span className="code dim">{r.code}</span>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {METRICS.map((m) => (
                <tr key={m.label}>
                  <td>{m.label}</td>
                  {rows.map((r) => (
                    <td key={r.code} className={m.align === 'right' ? 'right' : undefined}>
                      {m.render(r)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
