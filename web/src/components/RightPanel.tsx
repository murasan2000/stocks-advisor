import { Briefcase } from 'lucide-react'
import { MarketOverview } from './MarketOverview'
import { QuickActions } from './QuickActions'
import { RecentChats } from './RecentChats'
import type { Job } from '../types/api'

interface Props {
  recentJobs: Job[]
  jobsLoading: boolean
  isLoading: boolean
  activeJobId: string | null
  onQuickAction: (query: string) => void
  onLoadJob: (job: Job) => void
}

export function RightPanel({
  recentJobs,
  jobsLoading,
  isLoading,
  activeJobId,
  onQuickAction,
  onLoadJob,
}: Props) {
  return (
    <aside className="right-panel">
      <MarketOverview />

      <section className="panel-card panel-card--cta">
        <div className="portfolio-cta-icon">
          <Briefcase size={20} />
        </div>
        <div>
          <div className="portfolio-cta-title">ポートフォリオ分析</div>
          <div className="portfolio-cta-desc">楽天証券のCSVをアップロードして保有株を分析</div>
        </div>
        <button className="portfolio-cta-btn" disabled>近日公開</button>
      </section>

      <QuickActions onSelect={onQuickAction} disabled={isLoading} />

      <RecentChats
        jobs={recentJobs}
        loading={jobsLoading}
        activeJobId={activeJobId}
        onLoad={onLoadJob}
      />
    </aside>
  )
}
