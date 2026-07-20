import { useCallback, useState } from 'react'

/** 文字列キーの開閉集合を管理する（チャート等、複数同時に開ける項目向け）。 */
export function useToggleSet() {
  const [items, setItems] = useState<Set<string>>(new Set())

  const toggle = useCallback((key: string) => {
    setItems((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }, [])

  const remove = useCallback((key: string) => {
    setItems((prev) => {
      if (!prev.has(key)) return prev
      const next = new Set(prev)
      next.delete(key)
      return next
    })
  }, [])

  // 有効なキー集合に含まれない項目を取り除く。ウォッチ解除・保有銘柄削除・
  // CSV再インポート等、行が一覧から消える経路は複数あるため、個別の削除操作
  // ごとに掃除するのではなく、一覧の変化に追従してここで一括して整合させる
  // （消えた銘柄が後で再登録された際に、開いたままの状態で復活しないように）。
  const prune = useCallback((validKeys: Iterable<string>) => {
    const valid = validKeys instanceof Set ? validKeys : new Set(validKeys)
    setItems((prev) => {
      let changed = false
      const next = new Set(prev)
      for (const key of prev) {
        if (!valid.has(key)) {
          next.delete(key)
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [])

  return { items, toggle, remove, prune }
}
