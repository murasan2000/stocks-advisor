import { useCallback, useEffect, useRef, useState } from 'react'
import { createJob, getJob } from '../api/client'
import type { AgentKey, AgentStep, Job, JobStatus } from '../types/api'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  status?: JobStatus
  isError?: boolean
  progress?: AgentStep[]
}

const POLL_INTERVAL_MS = 1500
const POLL_TIMEOUT_MS = 330_000 // バックエンドのジョブタイムアウト(300s)より少し長く

// NOTE: crypto.randomUUID はセキュアコンテキスト（HTTPS または localhost）でのみ利用可能

export function useStocksAdvisor() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (pollTimer.current) clearTimeout(pollTimer.current)
    }
  }, [])

  const updateAssistant = useCallback(
    (id: string, patch: Partial<ChatMessage>) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...patch } : m)),
      )
    },
    [],
  )

  const sendQuery = useCallback(
    async (query: string, agents: AgentKey[] | null = null) => {
      if (!query.trim() || isLoading) return
      setIsLoading(true)

      const userMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'user',
        content: query,
      }
      const assistantId = crypto.randomUUID()
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: 'assistant',
        content: '',
        status: 'pending',
      }
      setMessages((prev) => [...prev, userMsg, assistantMsg])

      try {
        const { job_id } = await createJob(query, agents)
        const startedAt = Date.now()

        const poll = async () => {
          try {
            const job = await getJob(job_id)

            if (job.status === 'done') {
              updateAssistant(assistantId, {
                content: job.result ?? '(結果が空でした)',
                status: 'done',
                progress: job.progress ?? undefined,
              })
              setIsLoading(false)
              return
            }
            if (job.status === 'error') {
              updateAssistant(assistantId, {
                content: job.error ?? '不明なエラーが発生しました',
                status: 'error',
                isError: true,
                progress: job.progress ?? undefined,
              })
              setIsLoading(false)
              return
            }

            updateAssistant(assistantId, {
              status: job.status,
              progress: job.progress ?? undefined,
            })

            if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
              updateAssistant(assistantId, {
                content: 'タイムアウトしました。もう一度お試しください。',
                status: 'error',
                isError: true,
              })
              setIsLoading(false)
              return
            }
            pollTimer.current = setTimeout(poll, POLL_INTERVAL_MS)
          } catch (err) {
            updateAssistant(assistantId, {
              content: err instanceof Error ? err.message : String(err),
              status: 'error',
              isError: true,
            })
            setIsLoading(false)
          }
        }

        pollTimer.current = setTimeout(poll, POLL_INTERVAL_MS)
      } catch (err) {
        updateAssistant(assistantId, {
          content: err instanceof Error ? err.message : String(err),
          status: 'error',
          isError: true,
        })
        setIsLoading(false)
      }
    },
    [isLoading, updateAssistant],
  )

  const loadJob = useCallback(
    (job: Job) => {
      if (pollTimer.current) {
        clearTimeout(pollTimer.current)
        pollTimer.current = null
      }
      setIsLoading(false)
      setMessages([
        {
          id: crypto.randomUUID(),
          role: 'user',
          content: job.query,
        },
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content:
            job.status === 'done'
              ? (job.result ?? '(結果が空でした)')
              : job.status === 'error'
                ? (job.error ?? '不明なエラーが発生しました')
                : '',
          status: job.status,
          isError: job.status === 'error',
          progress: job.progress ?? undefined,
        },
      ])
    },
    [],
  )

  return { messages, isLoading, sendQuery, loadJob }
}
