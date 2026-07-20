import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Candle } from '../../types/api'
import { fmtPriceByCode } from '../../utils/format'
import { movingAverage } from '../../utils/technicals'

interface ChartRow extends Candle {
  range: [number, number]
  ma5: number | null
  ma25: number | null
  ma75: number | null
}

interface CandleShapeProps {
  x?: number
  y?: number
  width?: number
  height?: number
  payload?: ChartRow
}

// recharts のローソク足プリセットは無いため、range=[low, high] を Bar に渡して
// 高値-安値のピクセル幅を取得し、その中で始値/終値の位置を線形補間して描く。
function CandleShape(props: CandleShapeProps) {
  const { x = 0, y = 0, width = 0, height = 0, payload } = props
  if (!payload) return null
  const { open, high, low, close } = payload
  const up = close >= open
  const color = up ? 'var(--success)' : 'var(--error)'

  if (high <= low) {
    const midY = y + height / 2
    return <line x1={x} x2={x + width} y1={midY} y2={midY} stroke={color} strokeWidth={1} />
  }
  const scale = height / (high - low)
  const openY = y + (high - open) * scale
  const closeY = y + (high - close) * scale
  const bodyTop = Math.min(openY, closeY)
  const bodyHeight = Math.max(Math.abs(closeY - openY), 1)
  const wickX = x + width / 2
  const bodyX = x + width * 0.15
  const bodyWidth = width * 0.7

  return (
    <g>
      <line x1={wickX} x2={wickX} y1={y} y2={y + height} stroke={color} strokeWidth={1} />
      <rect x={bodyX} y={bodyTop} width={bodyWidth} height={bodyHeight} fill={color} />
    </g>
  )
}

interface TooltipPayloadItem {
  payload: ChartRow
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: TooltipPayloadItem[]
}) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="candle-tooltip">
      <div className="candle-tooltip-date">{d.date}</div>
      <div>始値 {d.open.toLocaleString('ja-JP')}</div>
      <div>高値 {d.high.toLocaleString('ja-JP')}</div>
      <div>安値 {d.low.toLocaleString('ja-JP')}</div>
      <div>終値 {d.close.toLocaleString('ja-JP')}</div>
      <div>出来高 {d.volume.toLocaleString('ja-JP')}</div>
    </div>
  )
}

interface Props {
  candles: Candle[]
  code: string
  // 保有銘柄の取得単価（ポートフォリオ画面から渡された場合のみラインを表示）
  avgCost?: number | null
}

export function CandlestickChart({ candles, code, avgCost }: Props) {
  const ma5 = movingAverage(candles, 5)
  const ma25 = movingAverage(candles, 25)
  const ma75 = movingAverage(candles, 75)
  const data: ChartRow[] = candles.map((c, i) => ({
    ...c,
    range: [c.low, c.high],
    ma5: ma5[i],
    ma25: ma25[i],
    ma75: ma75[i],
  }))
  const maxVolume = Math.max(...candles.map((c) => c.volume), 1)

  return (
    <div className="candle-chart">
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: 'var(--text-dim)' }}
            minTickGap={40}
          />
          <YAxis
            yAxisId="price"
            orientation="right"
            domain={['auto', 'auto']}
            tick={{ fontSize: 11, fill: 'var(--text-dim)' }}
            width={64}
          />
          {/* 出来高は独立軸のドメインを実際の最大値の3.5倍に広げ、
              チャート下部に小さく収める（価格チャートと重ねて1つの Chart にする定番の手法）。 */}
          <YAxis yAxisId="volume" domain={[0, maxVolume * 3.5]} hide />
          <Tooltip content={<ChartTooltip />} />
          {avgCost ? (
            <ReferenceLine
              yAxisId="price"
              y={avgCost}
              // 取得単価が表示中の期間の値幅から外れていても軸を広げて必ず表示する
              ifOverflow="extendDomain"
              stroke="var(--warning)"
              strokeDasharray="4 4"
              label={{
                value: `取得単価 ${fmtPriceByCode(code, avgCost)}`,
                position: 'insideTopLeft',
                fill: 'var(--warning)',
                fontSize: 11,
              }}
            />
          ) : null}
          <Bar yAxisId="volume" dataKey="volume" fill="var(--accent-1)" opacity={0.28} />
          <Bar yAxisId="price" dataKey="range" shape={CandleShape} />
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="ma5"
            stroke="var(--accent-3)"
            dot={false}
            strokeWidth={1.5}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="ma25"
            stroke="var(--accent-1)"
            dot={false}
            strokeWidth={1.5}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="ma75"
            stroke="var(--accent-2)"
            dot={false}
            strokeWidth={1.5}
            connectNulls
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="candle-legend">
        <span className="candle-legend-item"><i style={{ background: 'var(--accent-3)' }} />5日</span>
        <span className="candle-legend-item"><i style={{ background: 'var(--accent-1)' }} />25日</span>
        <span className="candle-legend-item"><i style={{ background: 'var(--accent-2)' }} />75日</span>
      </div>
    </div>
  )
}
