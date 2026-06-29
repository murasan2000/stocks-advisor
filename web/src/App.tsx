import { useEffect, useRef, useState } from 'react'
import { AgentSelector } from './components/AgentSelector'
import { AgentShowcase } from './components/AgentShowcase'
import { ChatInput } from './components/ChatInput'
import { MessageBubble } from './components/MessageBubble'
import { RightPanel } from './components/RightPanel'
import { Sidebar } from './components/Sidebar'
import { useRecentJobs } from './hooks/useRecentJobs'
import { useStocksAdvisor } from './hooks/useStocksAdvisor'
import type { AgentKey, Job } from './types/api'

export default function App() {
  const { messages, isLoading, sendQuery, loadJob } = useStocksAdvisor()
  const { jobs, loading: jobsLoading, refresh: refreshJobs } = useRecentJobs(10)
  const [inputValue, setInputValue] = useState('')
  const [selectedAgents, setSelectedAgents] = useState<AgentKey[]>([])
  const [activeJobId, setActiveJobId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (query: string) => {
    setActiveJobId(null)
    await sendQuery(query, selectedAgents)
    refreshJobs()
  }

  const handleQuickAction = (query: string) => {
    setInputValue(query)
  }

  const handleLoadJob = (job: Job) => {
    setActiveJobId(job.job_id)
    loadJob(job)
  }

  return (
    <div className="dashboard">
      <Sidebar />

      <main className="main-area">
        <div className="main-header">
          <div>
            <h2 className="main-greeting">こんにちは、Userさん</h2>
            <p className="main-subtitle">AI投資アドバイザー</p>
          </div>
          <span className="main-badge">AI 投資アドバイザー</span>
        </div>

        <div className="chat-area">
          {messages.length === 0 ? (
            <div className="empty-state">
              <div className="hero-glow" />
              <h2>なにを調べますか？</h2>
              <p>日本株・米国株の市況・財務・売買タイミングについて質問できます</p>
              <AgentShowcase
                selected={selectedAgents}
                onChange={setSelectedAgents}
                disabled={isLoading}
              />
            </div>
          ) : (
            <div className="messages">
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="main-footer">
          {messages.length > 0 && (
            <AgentSelector
              selected={selectedAgents}
              onChange={setSelectedAgents}
              disabled={isLoading}
            />
          )}
          <ChatInput
            value={inputValue}
            onChange={setInputValue}
            onSend={handleSend}
            disabled={isLoading}
          />
          <p className="disclaimer">
            AIによる情報提供であり、投資判断はご自身の責任で行ってください
          </p>
        </div>
      </main>

      <RightPanel
        recentJobs={jobs}
        jobsLoading={jobsLoading}
        isLoading={isLoading}
        activeJobId={activeJobId}
        onQuickAction={handleQuickAction}
        onLoadJob={handleLoadJob}
      />
    </div>
  )
}
