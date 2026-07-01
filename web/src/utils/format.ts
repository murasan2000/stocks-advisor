/** 表示用フォーマットユーティリティ。 */

export function fmtPrice(n: number | null): string {
  if (n === null) return '—'
  return `¥${n.toLocaleString('ja-JP', { maximumFractionDigits: 1 })}`
}

export function fmtPct(n: number | null): string {
  if (n === null) return '—'
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`
}

export function fmtNum(n: number | null, digits = 1): string {
  if (n === null) return '—'
  return n.toFixed(digits)
}

export function fmtMarketCap(n: number | null): string {
  if (n === null) return '—'
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}兆`
  if (n >= 1e8) return `${(n / 1e8).toFixed(0)}億`
  return n.toLocaleString('ja-JP')
}

export function fmtVolume(n: number | null): string {
  if (n === null) return '—'
  if (n >= 1e8) return `${(n / 1e8).toFixed(1)}億`
  if (n >= 1e4) return `${(n / 1e4).toFixed(1)}万`
  return n.toLocaleString('ja-JP')
}

export function fmtTimestamp(epoch: number | null): string {
  if (epoch === null) return '未取得'
  const d = new Date(epoch * 1000)
  const pad = (x: number) => String(x).padStart(2, '0')
  return (
    `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}`
  )
}
