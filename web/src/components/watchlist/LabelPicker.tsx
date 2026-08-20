import { Check, Tag, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Label } from '../../types/api'

interface Props {
  code: string
  stockName: string
  attachedIds: Set<string>
  allLabels: Label[]
  onAttach: (code: string, label: Label) => void
  onDetach: (code: string, labelId: string) => void
  onCreateAndAttach: (code: string, name: string) => Promise<void>
  onDeleteLabel: (labelId: string) => void
  onClose: () => void
}

/** 銘柄へのラベル付与・解除・新規作成をまとめて行うモーダル（issue #68）。
 * ReportCalendar と同じ導線（背景クリック・Escapeで閉じる）を踏襲する。 */
export function LabelPicker({
  code,
  stockName,
  attachedIds,
  allLabels,
  onAttach,
  onDetach,
  onCreateAndAttach,
  onDeleteLabel,
  onClose,
}: Props) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    setBusy(true)
    setError(null)
    try {
      await onCreateAndAttach(code, trimmed)
      setName('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="label-picker-overlay"
      role="dialog"
      aria-label="ラベルを選択"
      onPointerDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="label-picker-modal">
        <div className="label-picker-header">
          <span className="label-picker-title">
            <Tag size={13} />
            {stockName} にラベルを追加
          </span>
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

        <div className="label-picker-list">
          {allLabels.length === 0 ? (
            <p className="label-picker-empty">
              まだラベルがありません。下の欄から作成してください。
            </p>
          ) : (
            allLabels.map((l) => {
              const attached = attachedIds.has(l.label_id)
              return (
                <div key={l.label_id} className="label-picker-row">
                  <button
                    type="button"
                    className={`label-picker-item ${attached ? 'label-picker-item--attached' : ''}`}
                    onClick={() => (attached ? onDetach(code, l.label_id) : onAttach(code, l))}
                  >
                    <span className="label-picker-check">
                      {attached ? <Check size={13} /> : null}
                    </span>
                    {l.name}
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => onDeleteLabel(l.label_id)}
                    aria-label={`ラベル「${l.name}」自体を削除（全銘柄から解除されます）`}
                    title="ラベルを削除（全銘柄から解除）"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              )
            })
          )}
        </div>

        <form className="label-picker-create" onSubmit={(e) => void handleCreate(e)}>
          <input
            type="text"
            placeholder="新しいラベル名（例: 半導体）"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={40}
          />
          <button type="submit" disabled={busy || !name.trim()}>
            {busy ? '作成中…' : '作成'}
          </button>
        </form>
        {error ? <p className="label-picker-error">{error}</p> : null}
      </div>
    </div>
  )
}
