import { useCallback, useEffect, useRef, useState } from 'react'
import { getJob, getStocks, refreshSnapshot } from '../api/client'
import {
  EMPTY_FILTERS,
  type Filters,
  type ScreenerMeta,
  type ScreenerSummary,
  type StockRow,
} from '../types/api'

const DEBOUNCE_MS = 250
const POLL_MS = 1500
const MAX_POLLS = 1200 // 最大30分（全銘柄ライブ更新を想定）

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * スクリーニングのデータ取得を司るフック。
 * - フィルタ変更時に next_stage を辿って段階的に全件取得（途中経過も描画）。
 * - refresh() でスナップショット更新ジョブを起動し、完了後に再取得。
 */
export function useScreener() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS)
  const [stocks, setStocks] = useState<StockRow[]>([])
  const [summary, setSummary] = useState<ScreenerSummary | null>(null)
  const [meta, setMeta] = useState<ScreenerMeta | null>(null)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const runId = useRef(0)

  const load = useCallback(async (f: Filters) => {
    const myRun = ++runId.current
    setLoading(true)
    setError(null)
    try {
      const acc: StockRow[] = []
      let stage: number | null = 1
      let first = true
      while (stage !== null) {
        const res = await getStocks(f, stage)
        if (runId.current !== myRun) return // フィルタが変わったので破棄
        acc.push(...res.stocks)
        if (first) {
          setTotal(res.total)
          setSummary(res.summary)
          setMeta(res.meta)
          first = false
        }
        setStocks([...acc])
        stage = res.next_stage
      }
    } catch (e) {
      if (runId.current === myRun) {
        setError(e instanceof Error ? e.message : String(e))
      }
    } finally {
      if (runId.current === myRun) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => {
      void load(filters)
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [filters, load])

  const refresh = useCallback(async () => {
    setRefreshing(true)
    setError(null)
    try {
      const { job_id } = await refreshSnapshot()
      for (let i = 0; i < MAX_POLLS; i++) {
        await sleep(POLL_MS)
        const job = await getJob(job_id)
        if (job.status === 'done') break
        if (job.status === 'error') {
          throw new Error(job.error ?? 'スナップショット更新に失敗しました')
        }
      }
      await load(filters)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRefreshing(false)
    }
  }, [filters, load])

  return {
    filters,
    setFilters,
    stocks,
    summary,
    meta,
    total,
    loading,
    error,
    refreshing,
    refresh,
  }
}
