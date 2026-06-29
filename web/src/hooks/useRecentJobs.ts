import { useCallback, useEffect, useState } from 'react'
import { getJobs } from '../api/client'
import type { Job } from '../types/api'

export function useRecentJobs(limit = 10) {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getJobs(limit)
      setJobs(data)
    } catch {
      // silent - backend may not be running
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => {
    refresh()
  }, [refresh])

  return { jobs, loading, refresh }
}
