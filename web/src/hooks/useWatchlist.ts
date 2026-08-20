import { useCallback, useRef, useState } from 'react'
import {
  addToWatchlist,
  attachLabel,
  createLabel,
  deleteLabel as deleteLabelApi,
  detachLabel,
  getLabels,
  getWatchlist,
  getWatchlistCodes,
  removeFromWatchlist,
} from '../api/client'
import { useToggleSet } from './useToggleSet'
import type { Label, StockRow } from '../types/api'

/**
 * ウォッチリストの状態管理。
 * - watchedCodes: スクリーニング画面の★状態判定に使う軽量なコード集合。
 * - rows: ウォッチリスト画面表示用のスナップショット結合済み一覧（付与ラベル込み）。
 * - labels/selectedLabelIds: ラベルは並び順ではなく絞り込み用のタグとして扱う
 *   （issue #68。複数選択時はOR条件、呼び出し側で rows をフィルタする）。
 */
export function useWatchlist() {
  const [watchedCodes, setWatchedCodes] = useState<Set<string>>(new Set())
  const [rows, setRows] = useState<StockRow[]>([])
  const [loading, setLoading] = useState(false)
  const [labels, setLabels] = useState<Label[]>([])
  // 選択中の絞り込みラベル。汎用の開閉集合フック（WatchlistPage の openDetails 等と
  // 同じ）を再利用する。個別に分割代入し、以降は安定した関数参照として扱う
  // （WatchlistPage.tsx の pruneOpenDetails と同じ流儀）。
  const {
    items: selectedLabelIds,
    toggle: toggleLabelFilter,
    remove: removeLabelFilter,
  } = useToggleSet()
  // 同じコードへの連打で add/delete が競合しないよう、処理中のコードは無視する
  const pendingRef = useRef<Set<string>>(new Set())
  // ラベル操作（付与/解除/削除）の連打・多重発火ガード。キーは操作単位で分ける
  // （例: "attach:7203:xxx"）。同じキーの操作が進行中なら後続は無視する。これが無いと、
  // 同じ付与を2重に叩いた際、後発リクエストの失敗ロールバックが先発の成功を
  // 取り消してしまうレースが起こり得る（自己レビューで指摘）。
  const labelOpPendingRef = useRef<Set<string>>(new Set())

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

  const loadLabels = useCallback(async () => {
    try {
      setLabels(await getLabels())
    } catch {
      // 取得失敗時は前回表示していた一覧を残す（絞り込みチップが消えるだけで致命的ではない）
    }
  }, [])

  // 既存ラベルを銘柄へ付与する（楽観的更新。呼び出し側は labels 一覧から Label を渡す）。
  const attachLabelToCode = useCallback(async (code: string, label: Label) => {
    const opKey = `attach:${code}:${label.label_id}`
    if (labelOpPendingRef.current.has(opKey)) return
    labelOpPendingRef.current.add(opKey)
    setRows((prev) =>
      prev.map((r) =>
        r.code === code && !r.labels.some((l) => l.label_id === label.label_id)
          ? { ...r, labels: [...r.labels, label].sort((a, b) => a.name.localeCompare(b.name)) }
          : r,
      ),
    )
    try {
      await attachLabel(code, label.label_id)
    } catch {
      setRows((prev) =>
        prev.map((r) =>
          r.code === code
            ? { ...r, labels: r.labels.filter((l) => l.label_id !== label.label_id) }
            : r,
        ),
      )
    } finally {
      labelOpPendingRef.current.delete(opKey)
    }
  }, [])

  const detachLabelFromCode = useCallback(async (code: string, labelId: string) => {
    const opKey = `detach:${code}:${labelId}`
    if (labelOpPendingRef.current.has(opKey)) return
    labelOpPendingRef.current.add(opKey)
    // ロールバック用に、外した Label 自体を楽観的更新の中で捕捉しておく
    let removed: Label | undefined
    setRows((prev) =>
      prev.map((r) => {
        if (r.code !== code) return r
        removed = r.labels.find((l) => l.label_id === labelId)
        return { ...r, labels: r.labels.filter((l) => l.label_id !== labelId) }
      }),
    )
    try {
      await detachLabel(code, labelId)
    } catch {
      const restored = removed
      if (restored) {
        setRows((prev) =>
          prev.map((r) => (r.code === code ? { ...r, labels: [...r.labels, restored] } : r)),
        )
      }
    } finally {
      labelOpPendingRef.current.delete(opKey)
    }
  }, [])

  // 新規ラベルをその場作成して銘柄へ付与する（同名が既にあれば作成せず既存を再利用、バックエンドが冪等）。
  const createAndAttachLabel = useCallback(
    async (code: string, name: string) => {
      const label = await createLabel(name)
      setLabels((prev) =>
        prev.some((l) => l.label_id === label.label_id)
          ? prev
          : [...prev, label].sort((a, b) => a.name.localeCompare(b.name)),
      )
      await attachLabelToCode(code, label)
    },
    [attachLabelToCode],
  )

  // ラベル自体を削除する（全銘柄からの付与も連鎖して解除）。楽観的更新＋失敗時ロールバックだが、
  // rows/labels 全体をスナップショットへ丸ごと戻すと、削除リクエスト中に発生した他の変更
  // （別ラベルの付与/削除等）まで巻き戻してしまうため、このラベルに関する差分だけを
  // 個別に捕捉して復元する（自己レビューで指摘されたレース）。
  const deleteLabel = useCallback(
    async (labelId: string) => {
      const opKey = `delete:${labelId}`
      if (labelOpPendingRef.current.has(opKey)) return
      labelOpPendingRef.current.add(opKey)
      const removedLabel = labels.find((l) => l.label_id === labelId)
      const codesWithLabel = rows
        .filter((r) => r.labels.some((l) => l.label_id === labelId))
        .map((r) => r.code)
      setLabels((prev) => prev.filter((l) => l.label_id !== labelId))
      setRows((prev) =>
        prev.map((r) => ({ ...r, labels: r.labels.filter((l) => l.label_id !== labelId) })),
      )
      removeLabelFilter(labelId)
      try {
        await deleteLabelApi(labelId)
      } catch {
        const restored = removedLabel
        if (restored) {
          setLabels((prev) =>
            prev.some((l) => l.label_id === labelId)
              ? prev
              : [...prev, restored].sort((a, b) => a.name.localeCompare(b.name)),
          )
          setRows((prev) =>
            prev.map((r) =>
              codesWithLabel.includes(r.code) && !r.labels.some((l) => l.label_id === labelId)
                ? { ...r, labels: [...r.labels, restored].sort((a, b) => a.name.localeCompare(b.name)) }
                : r,
            ),
          )
        }
      } finally {
        labelOpPendingRef.current.delete(opKey)
      }
    },
    [labels, rows, removeLabelFilter],
  )

  return {
    watchedCodes,
    rows,
    loading,
    loadCodes,
    loadRows,
    add,
    toggle,
    labels,
    selectedLabelIds,
    loadLabels,
    attachLabelToCode,
    detachLabelFromCode,
    createAndAttachLabel,
    deleteLabel,
    toggleLabelFilter,
  }
}
