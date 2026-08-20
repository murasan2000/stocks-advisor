import { Plus, X } from 'lucide-react'
import type { StockRow } from '../../types/api'

interface Props {
  row: StockRow
  onOpenPicker: (code: string) => void
  onDetach: (code: string, labelId: string) => void
}

/** 銘柄行に付与済みラベルをバッジ表示し、追加導線（+）を出す（issue #68）。
 * 行自体がクリックで詳細開閉するため、バッジ操作は必ず stopPropagation する。 */
export function LabelBadges({ row, onOpenPicker, onDetach }: Props) {
  return (
    <div className="label-badges">
      {row.labels.map((l) => (
        <span key={l.label_id} className="label-badge">
          {l.name}
          <button
            type="button"
            className="label-badge-remove"
            onClick={(e) => {
              e.stopPropagation()
              onDetach(row.code, l.label_id)
            }}
            aria-label={`${row.name} から ${l.name} ラベルを解除`}
            title="ラベルを解除"
          >
            <X size={9} />
          </button>
        </span>
      ))}
      <button
        type="button"
        className="label-badge label-badge--add"
        onClick={(e) => {
          e.stopPropagation()
          onOpenPicker(row.code)
        }}
        aria-label={`${row.name} にラベルを追加`}
        title="ラベルを追加"
      >
        <Plus size={10} />
      </button>
    </div>
  )
}
