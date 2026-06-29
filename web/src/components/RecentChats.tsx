import { Clock } from 'lucide-react'
import type { Job } from '../types/api'

function relativeTime(ts: number): string {
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return 'たった今'
  if (diff < 3600) return `${Math.floor(diff / 60)}分前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}時間前`
  return `${Math.floor(diff / 86400)}日前`
}

function statusDot(status: Job['status']): string {
  if (status === 'done') return 'dot-done'
  if (status === 'error') return 'dot-error'
  return 'dot-active'
}

interface Props {
  jobs: Job[]
  loading: boolean
  activeJobId: string | null
  onLoad: (job: Job) => void
}

export function RecentChats({ jobs, loading, activeJobId, onLoad }: Props) {
  return (
    <section className="panel-card">
      <h3 className="panel-section-title">
        <Clock size={13} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
        最近のチャット
      </h3>
      {loading && <p className="recent-empty">読み込み中…</p>}
      {!loading && jobs.length === 0 && (
        <p className="recent-empty">チャット履歴はありません</p>
      )}
      <ul className="recent-list">
        {jobs.map((job) => (
          <li key={job.job_id} className="recent-item">
            <button
              className={`recent-item-btn ${activeJobId === job.job_id ? 'recent-item-btn--active' : ''}`}
              onClick={() => onLoad(job)}
              title={job.query}
            >
              <span className={`recent-dot ${statusDot(job.status)}`} />
              <span className="recent-query">{job.query}</span>
              <span className="recent-time">{relativeTime(job.created_at)}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
