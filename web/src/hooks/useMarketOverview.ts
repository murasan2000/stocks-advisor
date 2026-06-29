import { useCallback, useEffect, useState } from 'react'
import { getMarketOverview } from '../api/client'
import type { MarketOverview } from '../types/api'

/** 市場サマリー（Market Agent）を取得するフック。 */
export function useMarketOverview() {
  const [overview, setOverview] = useState<MarketOverview | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  // ボタン等から明示的に再取得する用（effect 外なので同期 setState で問題ない）。
  const refresh = useCallback(async () => {
    setLoading(true)
    setError(false)
    try {
      setOverview(await getMarketOverview())
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [])

  // 初回ロード。setState は then/catch/finally の非同期コールバック内で行う。
  useEffect(() => {
    let active = true
    getMarketOverview()
      .then((data) => {
        if (active) setOverview(data)
      })
      .catch(() => {
        if (active) setError(true)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  return { overview, loading, error, refresh }
}
