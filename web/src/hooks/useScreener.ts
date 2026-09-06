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
const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000 // 24時間: これを超えて古いスナップショットは自動更新する

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
  const autoRefreshTriggered = useRef(false) // マウント後の自動更新判定を1回だけ行うためのフラグ

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

  // マウント後、meta が取得できた時点で最終更新の鮮度を1回だけ判定し、
  // 古ければ自動でスナップショット更新を発火する（以後 meta が変わっても再判定しない）。
  useEffect(() => {
    if (autoRefreshTriggered.current || meta === null) return
    autoRefreshTriggered.current = true
    const isStale =
      meta.last_refresh === null || Date.now() - meta.last_refresh * 1000 > STALE_THRESHOLD_MS
    if (!isStale) return
    // effect内で直接setStateを呼ばないよう、refresh()の起動は次のタスクにずらす。
    const timer = setTimeout(() => {
      void refresh()
    }, 0)
    return () => clearTimeout(timer)
  }, [meta, refresh])

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
