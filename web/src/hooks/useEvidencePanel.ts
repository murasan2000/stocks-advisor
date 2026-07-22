import { useCallback, useRef, useState } from 'react'

const LOAD_TIMEOUT_MS = 4000

export interface EvidenceTarget {
  url: string
  title: string
}

/**
 * レポート内の出典リンクを右側パネルにiframeプレビューする状態管理（issue #56）。
 *
 * 検証の結果、X-Frame-Options/CSP による埋め込み拒否は iframe の load
 * イベントが発火してしまう（ブラウザが拒否用のエラーページ自体は「読み込み
 * 完了」として扱うため）ため、load の有無では埋め込み拒否を検出できない。
 * この blocked フラグはあくまで「一定時間 load 自体が発火しない」ケース
 * （DNS失敗・接続不可・応答なし等の真の読み込み失敗）だけを検出する。
 * 埋め込み拒否そのものは検出できない前提で、呼び出し側は常時「新しいタブで
 * 開く」導線を表示し、ユーザーがブラウザ側の挙動から自力で気づけるようにする。
 *
 * url は AI（Web検索結果）が返した信頼できない外部由来の文字列のため、
 * ここで http(s) 以外（javascript:/data: 等）を弾く。iframe の src・
 * 「新しいタブで開く」リンクの href の両方の唯一の入口がここになるため、
 * 呼び出し側（レポート内の出典リンク）を問わずこの一箇所で防御する。
 */
export function useEvidencePanel() {
  const [target, setTarget] = useState<EvidenceTarget | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [blocked, setBlocked] = useState(false)
  const currentUrlRef = useRef<string | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }

  const open = useCallback((url: string, title: string) => {
    if (!/^https?:\/\//i.test(url)) return
    // iframe は key={url} のため、同じURLを開いている最中に再度呼ばれても
    // 再読み込みされず load は再発火しない。ここで状態をリセットすると
    // 正常に表示済みのプレビューが「読み込み失敗」扱いになってしまうため、
    // URLが変わらない限りは何もしない。
    if (currentUrlRef.current === url) return
    currentUrlRef.current = url
    clearTimer()
    setTarget({ url, title })
    setLoaded(false)
    setBlocked(false)
    timerRef.current = setTimeout(() => {
      setBlocked(true)
    }, LOAD_TIMEOUT_MS)
  }, [])

  const close = useCallback(() => {
    currentUrlRef.current = null
    clearTimer()
    setTarget(null)
    setLoaded(false)
    setBlocked(false)
  }, [])

  const handleLoad = useCallback(() => {
    clearTimer()
    setLoaded(true)
    setBlocked(false)
  }, [])

  return { target, loaded, blocked, open, close, handleLoad }
}
