import type { Candle } from '../types/api'

/** 終値の単純移動平均を算出する（window 未満の区間は null）。 */
export function movingAverage(candles: Candle[], window: number): (number | null)[] {
  return candles.map((_, i) => {
    if (i + 1 < window) return null
    let sum = 0
    for (let j = i + 1 - window; j <= i; j++) sum += candles[j].close
    return sum / window
  })
}
