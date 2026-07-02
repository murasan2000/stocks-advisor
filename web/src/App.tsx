import { AiButton } from './components/chat/AiButton'
import { ChatModal } from './components/chat/ChatModal'
import { Sidebar } from './components/Sidebar'
import { FilterPanel } from './components/screener/FilterPanel'
import { ScreenerHeader } from './components/screener/ScreenerHeader'
import { StatCards } from './components/screener/StatCards'
import { StockTable } from './components/screener/StockTable'
import { useChat } from './hooks/useChat'
import { useScreener } from './hooks/useScreener'

export default function App() {
  const chat = useChat()
  const {
    filters,
    setFilters,
    stocks,
    summary,
    total,
    meta,
    loading,
    error,
    refreshing,
    refresh,
  } = useScreener()

  const handleSort = (key: string) => {
    setFilters({
      ...filters,
      sortBy: key,
      sortDesc: filters.sortBy === key ? !filters.sortDesc : true,
    })
  }

  return (
    <div className="app-shell">
      <Sidebar />

      <main className="screener-main">
        <ScreenerHeader
          meta={meta}
          total={total}
          q={filters.q}
          onSearch={(q) => setFilters({ ...filters, q })}
          refreshing={refreshing}
          onRefresh={refresh}
        />

        <StatCards summary={summary} />

        {error ? <div className="error-banner">{error}</div> : null}

        <div className="screener-body">
          <FilterPanel filters={filters} onChange={setFilters} />

          <section className="results">
            <div className="results-meta">
              <span className="results-count">
                {total.toLocaleString('ja-JP')} 件
              </span>
              {loading ? (
                <span className="loading-text">
                  読み込み中… ({stocks.length.toLocaleString('ja-JP')})
                </span>
              ) : null}
            </div>
            {loading ? (
              <div className="loading-bar">
                <span />
              </div>
            ) : null}
            <StockTable
              stocks={stocks}
              sortBy={filters.sortBy}
              sortDesc={filters.sortDesc}
              onSort={handleSort}
              loading={loading}
            />
          </section>
        </div>

        <p className="screener-disclaimer">
          ※本情報は投資判断の参考であり、投資勧誘を目的としたものではありません。投資判断はご自身の責任で行ってください。
        </p>
      </main>

      <AiButton onClick={chat.open} hidden={chat.isOpen} />
      <ChatModal chat={chat} />
    </div>
  )
}
