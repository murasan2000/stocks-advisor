import { useCallback, useRef, useState } from 'react'
import {
  createMarketReportJob,
  getJob,
  getMarketCategories,
  getMarketFx,
  getMarketReport,
  getMarketReportDates,
} from '../api/client'
import type { AgentStep, FxQuote, MarketCategoryInfo } from '../types/api'
import { todayIso } from '../utils/format'

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

// reports/取得済み判定は「カテゴリ×日付」単位でキャッシュする（issue #66）。
function reportKey(categoryId: string, date: string): string {
  return `${categoryId}:${date}`
}

/**
 * マーケット情報画面の状態管理。
 * - カテゴリ一覧・為替情報はプレーンな GET（Job不要）。
 * - レポートはカテゴリ×日付でDBに永続化される（issue #66）。本日分が未生成なら
 *   Job非同期＋ポーリングでAI生成し、過去日分はDBから即時取得する（Job不要）。
 *   同一（カテゴリ,日付）は一度取得したらセッション中キャッシュし、再取得しない。
 * - カレンダーで日付を選ぶと表示を切り替える。再実行（AI再生成・DB上書き）は
 *   本日分を表示している時のみ可能。
 */
export function useMarket() {
  const [categories, setCategories] = useState<MarketCategoryInfo[]>([])
  const [categoriesLoading, setCategoriesLoading] = useState(false)
  const [fx, setFx] = useState<FxQuote[]>([])
  const [fxLoading, setFxLoading] = useState(false)
  const [openCategory, setOpenCategory] = useState<string | null>(null)
  const [viewingDate, setViewingDate] = useState<string | null>(null)
  const [calendarOpen, setCalendarOpen] = useState(false)
  // カテゴリごとの「レポートが存在する日付一覧」（カレンダーの非活性判定用）
  const [availableDates, setAvailableDates] = useState<Record<string, string[]>>({})
  const [reports, setReports] = useState<Record<string, CategoryReport>>({})
  // 日付切替時、切り替え前のポーリングループが古い結果を書き込まないようにする。
  // await の直後は必ず再チェックしてから setState する（チェックと書き込みの間に
  // 別の generateReport 呼び出しが割り込むレースを防ぐため）。
  const runIdRef = useRef<Record<string, number>>({})
  // 取得済み（取得中含む）の reportKey。再取得要否の判定に使う
  // （reports state を直接見ると、ポーリング中の進捗更新のたびに関連コールバックの
  // identity が変わってしまうため、専用の ref で追跡する）。
  const fetchedRef = useRef<Set<string>>(new Set())
  // カテゴリの開閉シーケンス番号。toggleCategory の非同期処理（日付一覧取得→表示）
  // が完了する前に別カテゴリへ切り替わった場合、古い処理が viewingDate を
  // 上書きしないようにするためのガード。
  const openSeqRef = useRef(0)

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

  const patchReport = useCallback((key: string, patch: Partial<CategoryReport>) => {
    setReports((prev) => ({
      ...prev,
      [key]: { ...EMPTY_REPORT, ...prev[key], ...patch },
    }))
  }, [])

  const loadAvailableDates = useCallback(async (categoryId: string): Promise<string[]> => {
    try {
      const dates = await getMarketReportDates(categoryId)
      setAvailableDates((prev) => ({ ...prev, [categoryId]: dates }))
      return dates
    } catch {
      // 失敗時は state に記録しない（categoryId が availableDates に無いままにし、
      // 次回カテゴリを開いた際に再試行できるようにする。失敗を空配列として
      // 記録すると、以後ずっとカレンダーが「日付なし」のまま再取得されなくなる）。
      return []
    }
  }, [])

  // 本日分をAIで生成する（Job非同期＋ポーリング。完了時はバックエンド側でDBへ
  // upsertされる）。既に本日分がある場合も無条件に再実行し、DBの行を上書きする。
  const generateReport = useCallback(
    async (categoryId: string) => {
      const today = todayIso()
      const key = reportKey(categoryId, today)
      const myRun = (runIdRef.current[key] ?? 0) + 1
      runIdRef.current[key] = myRun
      fetchedRef.current.add(key)
      const isCurrent = () => runIdRef.current[key] === myRun
      patchReport(key, { content: null, progress: null, loading: true, error: null })
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
            patchReport(key, {
              content: job.result ?? 'レポートが空でした',
              progress: null,
              loading: false,
              error: null,
            })
            setAvailableDates((prev) => {
              const existing = prev[categoryId] ?? []
              if (existing.includes(today)) return prev
              return { ...prev, [categoryId]: [today, ...existing] }
            })
            return
          }
          if (job.status === 'error') {
            patchReport(key, {
              progress: job.progress ?? null, // どのステップで失敗したかを残す
              loading: false,
              error: job.error ?? 'レポート生成に失敗しました',
            })
            return
          }
          if (job.progress?.length) {
            patchReport(key, { progress: job.progress })
          }
          if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
            patchReport(key, {
              loading: false,
              error: 'タイムアウトしました。もう一度お試しください。',
            })
            return
          }
        }
      } catch (e) {
        if (!isCurrent()) return
        patchReport(key, {
          loading: false,
          error: e instanceof Error ? e.message : String(e),
        })
      }
    },
    [patchReport],
  )

  // カレンダーで日付を選ぶ／初回オープン時の表示切替。本日分でまだ何も無ければ
  // AI生成にフォールバックし、それ以外はDBから即時取得する（Job不要）。
  const viewDate = useCallback(
    async (categoryId: string, targetDate: string) => {
      setViewingDate(targetDate)
      setCalendarOpen(false)
      const today = todayIso()
      const hasSavedData = (availableDates[categoryId] ?? []).includes(targetDate)
      const key = reportKey(categoryId, targetDate)
      if (targetDate === today && !hasSavedData) {
        // 生成中/生成済みなら再実行しない（カレンダーの「本日」セルは常に押せる
        // ため、生成中に連打/再オープンしても二重にJobを作らないようにする）。
        if (fetchedRef.current.has(key)) return
        await generateReport(categoryId)
        return
      }
      if (fetchedRef.current.has(key)) return // 取得済み（取得中含む）
      fetchedRef.current.add(key)
      patchReport(key, { content: null, progress: null, loading: true, error: null })
      try {
        const report = await getMarketReport(categoryId, targetDate)
        patchReport(key, {
          content: report.content,
          progress: null,
          loading: false,
          error: null,
        })
      } catch (e) {
        fetchedRef.current.delete(key)
        patchReport(key, {
          loading: false,
          error: e instanceof Error ? e.message : String(e),
        })
      }
    },
    [availableDates, generateReport, patchReport],
  )

  // カテゴリボックス押下: 開いていれば畳む、閉じていれば開く。開く際は常に
  // 本日分を表示する（未生成なら自動でAI生成、既にあればDBの内容を表示）。
  const toggleCategory = useCallback(
    async (categoryId: string) => {
      setCalendarOpen(false)
      if (openCategory === categoryId) {
        openSeqRef.current += 1 // 開封中の非同期処理があれば無効化する
        setOpenCategory(null)
        setViewingDate(null)
        return
      }
      const mySeq = ++openSeqRef.current
      setOpenCategory(categoryId)
      if (!(categoryId in availableDates)) {
        await loadAvailableDates(categoryId)
      }
      // 日付一覧の取得中に別カテゴリへ切り替わっていたら、ここで打ち切る
      // （でなければ古いカテゴリの表示が新しいカテゴリの viewingDate を
      // 上書きしてしまう）。
      if (openSeqRef.current !== mySeq) return
      await viewDate(categoryId, todayIso())
    },
    [openCategory, availableDates, loadAvailableDates, viewDate],
  )

  const toggleCalendar = useCallback(() => {
    setCalendarOpen((v) => !v)
  }, [])

  return {
    categories,
    categoriesLoading,
    fx,
    fxLoading,
    openCategory,
    viewingDate,
    calendarOpen,
    availableDates,
    reports,
    reportKey,
    loadCategories,
    loadFx,
    toggleCategory,
    toggleCalendar,
    viewDate,
    generateReport,
  }
}
