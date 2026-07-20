import { useMemo, useState } from 'react'

/** クリックでソートキー/方向を切り替え、ソート済み配列を返す共通フック。 */
export function useSortState<T, K extends string>(
  rows: T[],
  compare: (a: T, b: T, key: K) => number,
  initialKey: K,
  initialDesc: boolean,
) {
  const [sortBy, setSortBy] = useState<K>(initialKey)
  const [sortDesc, setSortDesc] = useState(initialDesc)

  const sorted = useMemo(() => {
    const s = [...rows].sort((a, b) => compare(a, b, sortBy))
    return sortDesc ? s.reverse() : s
  }, [rows, compare, sortBy, sortDesc])

  const handleSort = (key: string) => {
    if (key === sortBy) {
      setSortDesc((d) => !d)
    } else {
      setSortBy(key as K)
      setSortDesc(true)
    }
  }

  return { sortBy, sortDesc, handleSort, sorted }
}
