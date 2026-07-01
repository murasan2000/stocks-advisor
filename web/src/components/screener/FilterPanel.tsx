import { RotateCcw } from 'lucide-react'
import {
  EMPTY_FILTERS,
  type Filters,
  MARKET_OPTIONS,
  PRESETS,
} from '../../types/api'

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
}

const OKU = 100_000_000 // 1億

export function FilterPanel({ filters, onChange }: Props) {
  const patch = (p: Partial<Filters>) => onChange({ ...filters, ...p })

  const num = (v: string): number | undefined =>
    v.trim() === '' ? undefined : Number(v)

  const toggleMarket = (m: string) =>
    patch({
      markets: filters.markets.includes(m)
        ? filters.markets.filter((x) => x !== m)
        : [...filters.markets, m],
    })

  return (
    <aside className="filter-panel">
      <div className="filter-head">
        <span className="filter-title">フィルター</span>
        <button
          type="button"
          className="filter-reset"
          onClick={() => onChange({ ...EMPTY_FILTERS })}
        >
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
              className="preset-chip"
              title={p.description}
              onClick={() => onChange(p.apply(filters))}
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
                checked={filters.markets.includes(m)}
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
              value={filters.perMin ?? ''}
              onChange={(e) => patch({ perMin: num(e.target.value) })}
            />
            <span>〜</span>
            <input
              type="number"
              placeholder="上限"
              value={filters.perMax ?? ''}
              onChange={(e) => patch({ perMax: num(e.target.value) })}
            />
          </div>
        </div>
        <div className="field-row">
          <label>PBR上限</label>
          <input
            type="number"
            placeholder="例: 1.5"
            value={filters.pbrMax ?? ''}
            onChange={(e) => patch({ pbrMax: num(e.target.value) })}
          />
        </div>
        <div className="field-row">
          <label>配当利回り下限(%)</label>
          <input
            type="number"
            placeholder="例: 3"
            value={filters.dividendYieldMin ?? ''}
            onChange={(e) => patch({ dividendYieldMin: num(e.target.value) })}
          />
        </div>
        <div className="field-row">
          <label>ROE下限(%)</label>
          <input
            type="number"
            placeholder="例: 10"
            value={filters.roeMin ?? ''}
            onChange={(e) => patch({ roeMin: num(e.target.value) })}
          />
        </div>
        <div className="field-row">
          <label>時価総額下限(億円)</label>
          <input
            type="number"
            placeholder="例: 1000"
            value={filters.marketCapMin ? filters.marketCapMin / OKU : ''}
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
            checked={filters.oversold}
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
            disabled={!filters.oversold}
            value={filters.dropFromHighPct}
            onChange={(e) => patch({ dropFromHighPct: Number(e.target.value) || 0 })}
          />
        </div>
        <div className="field-row">
          <label>1年安値からの反発(%)</label>
          <input
            type="number"
            disabled={!filters.oversold}
            value={filters.reboundFromLowPct}
            onChange={(e) =>
              patch({ reboundFromLowPct: Number(e.target.value) || 0 })
            }
          />
        </div>
      </div>
    </aside>
  )
}
