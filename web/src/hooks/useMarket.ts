import { useCallback, useRef, useState } from 'react'
import {
  createMarketReportJob,
  getJob,
  getMarketCategories,
  getMarketFx,
} from '../api/client'
import type { AgentStep, FxQuote, MarketCategoryInfo } from '../types/api'

const POLL_MS = 1200
const POLL_TIMEOUT_MS = 330_000 // バックエンドのエージェントタイムアウトより長め

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

export interface CategoryReport {
  content: string | null
  progress: AgentStep[] | null
  loading: boolean
  error: string | null
}

const EMPTY_REPORT: CategoryReport = { content: null, progress: null, loading: false, error: null }

/**
 * マーケット情報画面の状態管理。
 * - カテゴリ一覧・為替情報はプレーンな GET（Job不要）。
 * - カテゴリレポートは Job非同期＋ポーリング（チャットの企業分析と同じパターン）。
 *   一度取得したカテゴリは reports にキャッシュし、再クリックで再取得しない
 *   （開閉のトグルのみ行う。再取得したい場合は fetchReport を明示的に呼ぶ）。
 */
export function useMarket() {
  const [categories, setCategories] = useState<MarketCategoryInfo[]>([])
  const [categoriesLoading, setCategoriesLoading] = useState(false)
  const [fx, setFx] = useState<FxQuote[]>([])
  const [fxLoading, setFxLoading] = useState(false)
  const [openCategory, setOpenCategory] = useState<string | null>(null)
  const [reports, setReports] = useState<Record<string, CategoryReport>>({})
  // カテゴリ切替時、切り替え前のポーリングループが古い結果を書き込まないようにする。
  // await の直後は必ず再チェックしてから setState する（チェックと書き込みの間に
  // 別の fetchReport 呼び出しが割り込むレースを防ぐため）。
  const runIdRef = useRef<Record<string, number>>({})
  // 取得済み（取得中含む）のカテゴリID。toggleCategory の再取得要否判定に使う
  // （reports state を直接見ると、ポーリング中の進捗更新のたびに toggleCategory の
  // identity が変わってしまうため、専用の ref で追跡する）。
  const fetchedRef = useRef<Set<string>>(new Set())

  const loadCategories = useCallback(async () => {
    setCategoriesLoading(true)
    try {
      setCategories(await getMarketCategories())
    } catch {
      // 取得失敗時は前回表示していた一覧を残す（空に潰すとフェッチ失敗と
      // 「カテゴリ0件」が見分けられなくなるため）。
    } finally {
      setCategoriesLoading(false)
    }
  }, [])

  const loadFx = useCallback(async () => {
    setFxLoading(true)
    try {
      setFx(await getMarketFx())
    } catch {
      // 取得失敗時は前回表示していたクオートを残す（同上）。
    } finally {
      setFxLoading(false)
    }
  }, [])

  const patchReport = useCallback((categoryId: string, patch: Partial<CategoryReport>) => {
    setReports((prev) => ({
      ...prev,
      [categoryId]: { ...EMPTY_REPORT, ...prev[categoryId], ...patch },
    }))
  }, [])

  const fetchReport = useCallback(
    async (categoryId: string) => {
      const myRun = (runIdRef.current[categoryId] ?? 0) + 1
      runIdRef.current[categoryId] = myRun
      fetchedRef.current.add(categoryId)
      const isCurrent = () => runIdRef.current[categoryId] === myRun
      patchReport(categoryId, { content: null, progress: null, loading: true, error: null })
      try {
        const { job_id } = await createMarketReportJob(categoryId)
        if (!isCurrent()) return
        const startedAt = Date.now()
        for (;;) {
          await sleep(POLL_MS)
          if (!isCurrent()) return // 別のポーリングに切り替わった
          const job = await getJob(job_id)
          if (!isCurrent()) return // getJob 待機中に別のポーリングへ切り替わった
          if (job.status === 'done') {
            patchReport(categoryId, {
              content: job.result ?? 'レポートが空でした',
              progress: null,
              loading: false,
              error: null,
            })
            return
          }
          if (job.status === 'error') {
            patchReport(categoryId, {
              progress: job.progress ?? null, // どのステップで失敗したかを残す
              loading: false,
              error: job.error ?? 'レポート生成に失敗しました',
            })
            return
          }
          if (job.progress?.length) {
            patchReport(categoryId, { progress: job.progress })
          }
          if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
            patchReport(categoryId, {
              loading: false,
              error: 'タイムアウトしました。もう一度お試しください。',
            })
            return
          }
        }
      } catch (e) {
        if (!isCurrent()) return
        patchReport(categoryId, {
          loading: false,
          error: e instanceof Error ? e.message : String(e),
        })
      }
    },
    [patchReport],
  )

  // カテゴリボックス押下: 開いていれば畳む、閉じていれば開く（未取得ならレポートも取得）。
  const toggleCategory = useCallback(
    (categoryId: string) => {
      setOpenCategory((prev) => (prev === categoryId ? null : categoryId))
      if (!fetchedRef.current.has(categoryId)) {
        void fetchReport(categoryId)
      }
    },
    [fetchReport],
  )

  return {
    categories,
    categoriesLoading,
    fx,
    fxLoading,
    openCategory,
    reports,
    loadCategories,
    loadFx,
    toggleCategory,
    fetchReport,
  }
}
