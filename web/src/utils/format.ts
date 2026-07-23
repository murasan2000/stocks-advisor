/** 表示用フォーマットユーティリティ。 */

// バックエンドの is_jp_code（api/app/utils/market.py）と同じ判定ルール。
// 日本株コード（4桁、先頭3桁が数字）以外は米国株ティッカーとして扱う。
const JP_CODE_RE = /^\d{3}[0-9A-Z]$/

export function isJpCode(code: string): boolean {
  return JP_CODE_RE.test(code.trim().toUpperCase())
}

export function fmtPrice(n: number | null): string {
  if (n === null) return '—'
  return `¥${n.toLocaleString('ja-JP', { maximumFractionDigits: 1 })}`
}

export function fmtPriceUsd(n: number | null): string {
  if (n === null) return '—'
  return `$${n.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
}

/** 銘柄コードに応じて円/ドル表示を切り替える価格フォーマット。 */
export function fmtPriceByCode(code: string, n: number | null): string {
  return isJpCode(code) ? fmtPrice(n) : fmtPriceUsd(n)
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

/** 銘柄コードに応じて円（兆/億）/ドル（T/B/M）表示を切り替える時価総額フォーマット。
 *
 * しきい値は各桁の丸め表示で繰り上がる境界（例: 999.5M は "1.0B" 側）に合わせてあり、
 * 単純に 1e9 等で区切ると "$1000M" のような表示になってしまう問題を避けている。
 */
export function fmtMarketCapByCode(code: string, n: number | null): string {
  if (n === null) return '—'
  if (isJpCode(code)) return fmtMarketCap(n)
  if (n >= 999_500_000_000) return `$${(n / 1e12).toFixed(2)}T`
  if (n >= 999_500_000) return `$${(n / 1e9).toFixed(1)}B`
  if (n >= 999_500) return `$${(n / 1e6).toFixed(0)}M`
  return `$${n.toLocaleString('en-US')}`
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

/** 端末ローカル日時から YYYY-MM-DD を作る（カレンダーのセル計算等、任意のY/M/Dを
 * ローカルタイムゾーンで文字列化したい場合に使う）。 */
export function dateToIso(d: Date): string {
  const pad = (x: number) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// 本アプリは日本株市場が主対象のため、「今日」は常にJST基準で判定する
// （バックエンドの app/utils/dates.py の today_jst() と揃える）。ブラウザの
// ローカルタイムゾーンに依存すると、サーバがUTC等でホストされた場合に
// マーケットレポートの日付キーがサーバ側とずれてしまうため。
export function todayIso(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

/** YYYY-MM-DD を日本語の日付表示に整形する（例: "2026年7月23日"）。 */
export function fmtIsoDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return iso
  return `${y}年${m}月${d}日`
}
