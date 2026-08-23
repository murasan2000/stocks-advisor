import { Sparkles, X } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { AiButton } from './components/chat/AiButton'
import { ChatModal } from './components/chat/ChatModal'
import { ChatToast } from './components/chat/ChatToast'
import { Sidebar } from './components/Sidebar'
import { MarketPage } from './components/market/MarketPage'
import { PortfolioPage } from './components/portfolio/PortfolioPage'
import { FilterPanel, type PanelFilters } from './components/screener/FilterPanel'
import { ScreenerHeader } from './components/screener/ScreenerHeader'
import { StatCards } from './components/screener/StatCards'
import { StockTable } from './components/screener/StockTable'
import { WatchlistPage } from './components/watchlist/WatchlistPage'
import { useChat } from './hooks/useChat'
import { useMarket } from './hooks/useMarket'
import { usePortfolio } from './hooks/usePortfolio'
import { useScreener } from './hooks/useScreener'
import { useWatchlist } from './hooks/useWatchlist'

export type View = 'screener' | 'watchlist' | 'portfolio' | 'market'

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
  const {
    watchedCodes,
    rows: watchlistRows,
    loading: watchlistLoading,
    loadCodes: loadWatchlistCodes,
    loadRows: loadWatchlistRows,
    add: addWatch,
    toggle: toggleWatch,
    labels: watchlistLabels,
    selectedLabelIds: selectedWatchlistLabelIds,
    loadLabels: loadWatchlistLabels,
    attachLabelToCode,
    detachLabelFromCode,
    createAndAttachLabel,
    deleteLabel: deleteWatchlistLabel,
    toggleLabelFilter: toggleWatchlistLabelFilter,
  } = useWatchlist()
  const {
    holdings,
    loading: portfolioLoading,
    error: portfolioError,
    loadHoldings,
    addHolding,
    removeHolding,
    importCsv,
  } = usePortfolio()
  const market = useMarket()
  const { loadCategories: loadMarketCategories, loadFx: loadMarketFx } = market
  const [view, setView] = useState<View>('screener')
  // 企業分析の対象として選択中の銘柄コード
  const [selected, setSelected] = useState<Set<string>>(new Set())

  // ★状態はどちらの画面でも必要なため、起動時に一度だけ取得する
  useEffect(() => {
    void loadWatchlistCodes()
  }, [loadWatchlistCodes])

  const handleChangeView = useCallback(
    (next: View) => {
      setView(next)
      if (next === 'watchlist') {
        void loadWatchlistRows()
        void loadWatchlistLabels()
      }
      if (next === 'portfolio') void loadHoldings()
      if (next === 'market') {
        void loadMarketCategories()
        void loadMarketFx()
      }
    },
    [loadWatchlistRows, loadWatchlistLabels, loadHoldings, loadMarketCategories, loadMarketFx],
  )

  // 検索語の反映。関数更新にして恒常的に同一 identity を保ち、
  // ScreenerHeader 側のデバウンスが無関係な再描画でリセットされないようにする。
  const handleSearch = useCallback((q: string) => {
    setFilters((prev) => ({ ...prev, q }))
  }, [setFilters])

  // フィルターパネルの「適用」。パネル項目のみ反映し、検索語・ソートは維持する。
  const handleApplyFilters = useCallback(
    (panel: PanelFilters) => {
      setFilters((prev) => ({ ...prev, ...panel }))
    },
    [setFilters],
  )

  const handleSort = (key: string) => {
    setFilters({
      ...filters,
      sortBy: key,
      sortDesc: filters.sortBy === key ? !filters.sortDesc : true,
    })
  }

  const toggleSelect = (code: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(code)) {
        next.delete(code)
      } else {
        next.add(code)
      }
      return next
    })
  }

  const handleAnalyze = () => {
    // 送信中は受け付けない（選択を消したのに分析が走らない事故を防ぐ）
    if (chat.busy) return
    const codes = [...selected]
    setSelected(new Set())
    void chat.analyzeTickers(codes)
  }

  return (
    <div className="app-shell">
      <Sidebar view={view} onChangeView={handleChangeView} />

      {view === 'watchlist' ? (
        <WatchlistPage
          rows={watchlistRows}
          loading={watchlistLoading}
          watchedCodes={watchedCodes}
          onToggleWatch={toggleWatch}
          selected={selected}
          onToggleSelect={toggleSelect}
          onAdd={addWatch}
          labels={watchlistLabels}
          selectedLabelIds={selectedWatchlistLabelIds}
          onAttachLabel={attachLabelToCode}
          onDetachLabel={detachLabelFromCode}
          onCreateAndAttachLabel={createAndAttachLabel}
          onDeleteLabel={deleteWatchlistLabel}
          onToggleLabelFilter={toggleWatchlistLabelFilter}
        />
      ) : view === 'portfolio' ? (
        <PortfolioPage
          holdings={holdings}
          loading={portfolioLoading}
          error={portfolioError}
          onAdd={addHolding}
          onRemove={removeHolding}
          onImportCsv={importCsv}
          watchedCodes={watchedCodes}
          onToggleWatch={toggleWatch}
          selected={selected}
          onToggleSelect={toggleSelect}
          stocks={stocks}
        />
      ) : view === 'market' ? (
        <MarketPage market={market} />
      ) : (
        <main className="screener-main">
          <ScreenerHeader
            meta={meta}
            total={total}
            q={filters.q}
            onSearch={handleSearch}
            refreshing={refreshing}
            onRefresh={refresh}
          />

          <StatCards summary={summary} />

          {error ? <div className="error-banner">{error}</div> : null}

          <div className="screener-body">
            <FilterPanel filters={filters} onApply={handleApplyFilters} />

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
                selected={selected}
                onToggleSelect={toggleSelect}
                watchedCodes={watchedCodes}
                onToggleWatch={toggleWatch}
              />
            </section>
          </div>

          <p className="screener-disclaimer">
            ※本情報は投資判断の参考であり、投資勧誘を目的としたものではありません。投資判断はご自身の責任で行ってください。
          </p>
        </main>
      )}

      {selected.size > 0 ? (
        <div className="select-action-bar">
          <span className="select-action-count">
            {selected.size} 銘柄を選択中（{[...selected].join(', ')}）
          </span>
          <button
            type="button"
            className="select-action-analyze"
            onClick={handleAnalyze}
            disabled={chat.busy}
          >
            <Sparkles size={15} />
            AIで企業分析
          </button>
          <button
            type="button"
            className="chat-icon-btn"
            onClick={() => setSelected(new Set())}
            aria-label="選択を解除"
            title="選択を解除"
          >
            <X size={16} />
          </button>
        </div>
      ) : null}

      {chat.notice && !chat.isOpen ? (
        <ChatToast
          notice={chat.notice}
          onOpen={chat.open}
          onDismiss={chat.clearNotice}
        />
      ) : null}
      <AiButton onClick={chat.open} hidden={chat.isOpen} />
      <ChatModal chat={chat} />
    </div>
  )
}
