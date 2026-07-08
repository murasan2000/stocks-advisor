import { Check, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import {
  EMPTY_FILTERS,
  type Filters,
  MARKET_OPTIONS,
  type Preset,
  PRESETS,
} from '../../types/api'

/** フィルターパネルが扱う項目（検索テキスト・ソートは対象外）。 */
export type PanelFilters = Omit<Filters, 'q' | 'sortBy' | 'sortDesc'>

interface Props {
  filters: Filters
  /** 「適用」押下時にパネル項目のみ反映する（q・ソートは変更しない）。 */
  onApply: (panel: PanelFilters) => void
}

const OKU = 100_000_000 // 1億

const toPanel = (f: Filters): PanelFilters => ({
  markets: f.markets,
  perMin: f.perMin,
  perMax: f.perMax,
  pbrMax: f.pbrMax,
  dividendYieldMin: f.dividendYieldMin,
  roeMin: f.roeMin,
  marketCapMin: f.marketCapMin,
  oversold: f.oversold,
  dropFromHighPct: f.dropFromHighPct,
  reboundFromLowPct: f.reboundFromLowPct,
})

// markets は選択順に依存させない（並びが違うだけで「未適用」扱いにしない）
const normalize = (p: PanelFilters): PanelFilters => ({
  ...toPanel({ ...EMPTY_FILTERS, ...p }),
  markets: [...p.markets].sort(),
})

const samePanel = (a: PanelFilters, b: PanelFilters): boolean =>
  JSON.stringify(normalize(a)) === JSON.stringify(normalize(b))

/** プリセットを draft に適用した結果（パネル項目のみ）。 */
const applyPreset = (p: Preset, draft: PanelFilters): PanelFilters =>
  toPanel(p.apply({ ...EMPTY_FILTERS, ...draft }))

/** プリセットが設定する項目（EMPTY との差分キー）。トグル解除に使う。 */
const presetKeys = (p: Preset): (keyof PanelFilters)[] => {
  const base = toPanel(EMPTY_FILTERS)
  const applied = toPanel(p.apply({ ...EMPTY_FILTERS }))
  return (Object.keys(applied) as (keyof PanelFilters)[]).filter(
    (k) => JSON.stringify(applied[k]) !== JSON.stringify(base[k]),
  )
}

export function FilterPanel({ filters, onApply }: Props) {
  // 変更は draft に保持し、「適用」押下で初めて検索を実行する（#27）
  const [draft, setDraft] = useState<PanelFilters>(() => toPanel(filters))
  const dirty = !samePanel(draft, toPanel(filters))

  const patch = (p: Partial<PanelFilters>) => setDraft({ ...draft, ...p })

  const num = (v: string): number | undefined =>
    v.trim() === '' ? undefined : Number(v)

  const toggleMarket = (m: string) =>
    patch({
      markets: draft.markets.includes(m)
        ? draft.markets.filter((x) => x !== m)
        : [...draft.markets, m],
    })

  // プリセットの条件がすべて draft に反映済みならアクティブ表示（#26）
  const isPresetActive = (p: Preset) => samePanel(applyPreset(p, draft), draft)

  const togglePreset = (p: Preset) => {
    if (isPresetActive(p)) {
      // 解除: プリセットが設定する項目を初期値に戻す
      const cleared = { ...draft }
      const empty = toPanel(EMPTY_FILTERS)
      for (const k of presetKeys(p)) {
        // キーごとの代入は TS がユニオン型を絞り込めないため Record 経由で戻す
        ;(cleared as Record<string, unknown>)[k] = empty[k]
      }
      setDraft(cleared)
    } else {
      setDraft(applyPreset(p, draft))
    }
  }

  const reset = () => {
    // リセットは従来どおり即時反映（draft も初期化）
    const empty = toPanel(EMPTY_FILTERS)
    setDraft(empty)
    onApply(empty)
  }

  return (
    <aside className="filter-panel">
      <div className="filter-head">
        <span className="filter-title">フィルター</span>
        <button type="button" className="filter-reset" onClick={reset}>
          <RotateCcw size={13} /> リセット
        </button>
      </div>

      <div className="filter-group">
        <div className="filter-group-title">プリセット</div>
        <div className="preset-grid">
          {PRESETS.map((p) => (
            <button
              key={p.key}
              type="button"
              className={`preset-chip ${isPresetActive(p) ? 'preset-chip--active' : ''}`}
              title={p.description}
              onClick={() => togglePreset(p)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <div className="filter-group-title">市場</div>
        <div className="market-checks">
          {MARKET_OPTIONS.map((m) => (
            <label key={m} className="check">
              <input
                type="checkbox"
                checked={draft.markets.includes(m)}
                onChange={() => toggleMarket(m)}
              />
              <span>{m}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="filter-group">
        <div className="filter-group-title">バリュエーション</div>
        <div className="field-row">
          <label>PER</label>
          <div className="range-inputs">
            <input
              type="number"
              placeholder="下限"
              value={draft.perMin ?? ''}
              onChange={(e) => patch({ perMin: num(e.target.value) })}
            />
            <span>〜</span>
            <input
              type="number"
              placeholder="上限"
              value={draft.perMax ?? ''}
              onChange={(e) => patch({ perMax: num(e.target.value) })}
            />
          </div>
        </div>
        <div className="field-row">
          <label>PBR上限</label>
          <input
            type="number"
            placeholder="例: 1.5"
            value={draft.pbrMax ?? ''}
            onChange={(e) => patch({ pbrMax: num(e.target.value) })}
          />
        </div>
        <div className="field-row">
          <label>配当利回り下限(%)</label>
          <input
            type="number"
            placeholder="例: 3"
            value={draft.dividendYieldMin ?? ''}
            onChange={(e) => patch({ dividendYieldMin: num(e.target.value) })}
          />
        </div>
        <div className="field-row">
          <label>ROE下限(%)</label>
          <input
            type="number"
            placeholder="例: 10"
            value={draft.roeMin ?? ''}
            onChange={(e) => patch({ roeMin: num(e.target.value) })}
          />
        </div>
        <div className="field-row">
          <label>時価総額下限(億円)</label>
          <input
            type="number"
            placeholder="例: 1000"
            value={draft.marketCapMin ? draft.marketCapMin / OKU : ''}
            onChange={(e) => {
              const v = num(e.target.value)
              patch({ marketCapMin: v === undefined ? undefined : v * OKU })
            }}
          />
        </div>
      </div>

      <div className="filter-group">
        <div className="filter-group-title">下がりすぎ反発検出</div>
        <label className="check check--toggle">
          <input
            type="checkbox"
            checked={draft.oversold}
            onChange={(e) => patch({ oversold: e.target.checked })}
          />
          <span>有効にする</span>
        </label>
        <p className="filter-hint">
          5年高値から大きく下落し、直近で底を打って反発し始めた銘柄を抽出します。
        </p>
        <div className="field-row">
          <label>5年高値からの下落(%)</label>
          <input
            type="number"
            disabled={!draft.oversold}
            value={draft.dropFromHighPct}
            onChange={(e) => patch({ dropFromHighPct: Number(e.target.value) || 0 })}
          />
        </div>
        <div className="field-row">
          <label>1年安値からの反発(%)</label>
          <input
            type="number"
            disabled={!draft.oversold}
            value={draft.reboundFromLowPct}
            onChange={(e) =>
              patch({ reboundFromLowPct: Number(e.target.value) || 0 })
            }
          />
        </div>
      </div>

      <button
        type="button"
        className={`filter-apply ${dirty ? 'filter-apply--dirty' : ''}`}
        onClick={() => onApply(draft)}
        disabled={!dirty}
      >
        <Check size={15} />
        {dirty ? 'フィルターを適用' : '適用済み'}
      </button>
    </aside>
  )
}
