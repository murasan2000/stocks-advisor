import type { ReactNode } from 'react'

interface Props {
  label: string
  count: number
  children: ReactNode
}

/** 日本株/米国株の表示分割セクション（通貨が異なるため混在表示しない）。件数0なら非表示。 */
export function MarketSection({ label, count, children }: Props) {
  if (count === 0) return null
  return (
    <section className="market-section">
      <h2 className="market-section-title">
        {label}
        <span className="market-section-count">{count}</span>
      </h2>
      {children}
    </section>
  )
}
