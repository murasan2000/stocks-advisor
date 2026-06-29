import { Line, LineChart, ResponsiveContainer } from 'recharts'

interface MarketItem {
  name: string
  value: string
  change: string
  up: boolean
  data: { v: number }[]
}

const MARKETS: MarketItem[] = [
  {
    name: '日経平均',
    value: '39,150',
    change: '+0.85%',
    up: true,
    data: [38000, 38200, 37800, 38500, 38900, 38600, 39100, 38800, 39300, 39150].map((v) => ({ v })),
  },
  {
    name: 'TOPIX',
    value: '2,745',
    change: '+0.42%',
    up: true,
    data: [2680, 2695, 2660, 2710, 2730, 2720, 2750, 2735, 2760, 2745].map((v) => ({ v })),
  },
  {
    name: 'USD/JPY',
    value: '159.10',
    change: '+0.52%',
    up: true,
    data: [156.2, 155.8, 157.1, 156.5, 157.8, 158.2, 157.5, 158.9, 158.4, 159.1].map((v) => ({ v })),
  },
  {
    name: 'S&P 500',
    value: '5,320',
    change: '-0.38%',
    up: false,
    data: [5100, 5150, 5080, 5200, 5280, 5220, 5310, 5260, 5350, 5320].map((v) => ({ v })),
  },
]

export function MarketOverview() {
  return (
    <section className="panel-card">
      <h3 className="panel-section-title">市場概況</h3>
      <div className="market-list">
        {MARKETS.map((m) => (
          <div key={m.name} className="market-item">
            <div className="market-item-info">
              <span className="market-item-name">{m.name}</span>
              <span className="market-item-value">{m.value}</span>
              <span className={`market-item-change ${m.up ? 'up' : 'down'}`}>
                {m.change}
              </span>
            </div>
            <div className="market-sparkline">
              <ResponsiveContainer width="100%" height={36}>
                <LineChart data={m.data}>
                  <Line
                    type="monotone"
                    dataKey="v"
                    stroke={m.up ? '#22c55e' : '#ef4444'}
                    strokeWidth={1.5}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </div>
      <p className="market-disclaimer">※ダミーデータ</p>
    </section>
  )
}
