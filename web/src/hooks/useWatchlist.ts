import { useCallback, useRef, useState } from 'react'
import {
  addToWatchlist,
  getWatchlist,
  getWatchlistCodes,
  removeFromWatchlist,
} from '../api/client'
import type { StockRow } from '../types/api'

/**
 * ウォッチリストの状態管理。
 * - watchedCodes: スクリーニング画面の★状態判定に使う軽量なコード集合。
 * - rows: ウォッチリスト画面表示用のスナップショット結合済み一覧。
 */
export function useWatchlist() {
  const [watchedCodes, setWatchedCodes] = useState<Set<string>>(new Set())
  const [rows, setRows] = useState<StockRow[]>([])
  const [loading, setLoading] = useState(false)
  // 同じコードへの連打で add/delete が競合しないよう、処理中のコードは無視する
  const pendingRef = useRef<Set<string>>(new Set())

  const loadCodes = useCallback(async () => {
    try {
      setWatchedCodes(new Set(await getWatchlistCodes()))
    } catch {
      // 取得失敗時は星が全て未登録表示になるだけで致命的ではないため無視する
    }
  }, [])

  const loadRows = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getWatchlist()
      setRows(data)
      setWatchedCodes(new Set(data.map((r) => r.code)))
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  // コード直接入力での追加（★ボタンと異なり、追加後は quote 反映のため一覧を再取得する）
  const add = useCallback(
    async (code: string) => {
      await addToWatchlist(code)
      await loadRows()
    },
    [loadRows],
  )

  const toggle = useCallback(async (code: string) => {
    // 連打で add/delete のリクエストが競合しないよう、処理中は無視する
    if (pendingRef.current.has(code)) return
    pendingRef.current.add(code)

    const wasWatched = watchedCodes.has(code)
    // 楽観的更新（クリック即座に見た目を変え、失敗時はロールバック）
    setWatchedCodes((prev) => {
      const next = new Set(prev)
      if (wasWatched) next.delete(code)
      else next.add(code)
      return next
    })
    try {
      if (wasWatched) {
        await removeFromWatchlist(code)
        setRows((prev) => prev.filter((r) => r.code !== code))
      } else {
        await addToWatchlist(code)
      }
    } catch {
      setWatchedCodes((prev) => {
        const next = new Set(prev)
        if (wasWatched) next.add(code)
        else next.delete(code)
        return next
      })
    } finally {
      pendingRef.current.delete(code)
    }
  }, [watchedCodes])

  return { watchedCodes, rows, loading, loadCodes, loadRows, add, toggle }
}
