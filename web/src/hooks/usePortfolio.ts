import { useCallback, useState } from 'react'
import {
  getHoldings,
  importHoldingsCsv,
  removeHolding,
  upsertHolding,
} from '../api/client'
import type { Holding } from '../types/api'

/** 保有銘柄（ポートフォリオ）の状態管理。 */
export function usePortfolio() {
  const [holdings, setHoldings] = useState<Holding[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadHoldings = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setHoldings(await getHoldings())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const addHolding = useCallback(
    async (code: string, quantity: number, avgCost: number) => {
      await upsertHolding(code, quantity, avgCost)
      await loadHoldings()
    },
    [loadHoldings],
  )

  const removeHoldingByCode = useCallback(async (code: string) => {
    try {
      await removeHolding(code)
      setHoldings((prev) => prev.filter((h) => h.code !== code))
    } catch (e) {
      // 失敗時は行を残したまま、エラーバナーで気付けるようにする
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  const importCsv = useCallback(
    async (file: File) => {
      const result = await importHoldingsCsv(file)
      await loadHoldings()
      return result
    },
    [loadHoldings],
  )

  return {
    holdings,
    loading,
    error,
    loadHoldings,
    addHolding,
    removeHolding: removeHoldingByCode,
    importCsv,
  }
}
