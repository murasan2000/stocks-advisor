import type { AgentKey, CreateJobResponse, Job } from '../types/api'

const BASE_URL = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw new Error(`API error ${res.status}: ${body || res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function createJob(
  query: string,
  agents: AgentKey[] | null = null,
): Promise<CreateJobResponse> {
  return request<CreateJobResponse>('/jobs', {
    method: 'POST',
    // agents が空配列のときはフルパイプライン（null 扱い）
    body: JSON.stringify({
      query,
      agents: agents && agents.length > 0 ? agents : null,
    }),
  })
}

export function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/jobs/${jobId}`)
}

export function getJobs(limit = 10): Promise<Job[]> {
  return request<Job[]>(`/jobs?limit=${limit}`)
}
