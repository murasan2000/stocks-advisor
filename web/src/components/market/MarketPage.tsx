import { AlertCircle, ArrowDownRight, ArrowUpRight, Minus, RefreshCw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AgentProgress } from '../chat/AgentProgress'
import type { CategoryReport, useMarket } from '../../hooks/useMarket'
import { fmtNum, fmtPct } from '../../utils/format'

// AI回答と同じ方針（XSS対策で生HTMLは許可しない。リンクは別タブで開く）。
const MARKDOWN_COMPONENTS = {
  a: ({ href, children }: React.ComponentProps<'a'>) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
}

interface Props {
  market: ReturnType<typeof useMarket>
}

export function MarketPage({ market }: Props) {
  const {
    categories,
    categoriesLoading,
    fx,
    fxLoading,
    openCategory,
    reports,
    loadFx,
    toggleCategory,
    fetchReport,
  } = market
  const openLabel = categories.find((c) => c.id === openCategory)?.label ?? ''
  const openReport = openCategory ? reports[openCategory] : undefined

  return (
    <main className="screener-main">
      <header className="screener-header-title">
        <h1>マーケット</h1>
        <p>カテゴリを選択するとAIが収集した最新の市況レポートを表示します。</p>
      </header>

      <div className="market-body">
        <section className="market-categories">
          {categoriesLoading && categories.length === 0 ? (
            <div className="loading-bar">
              <span />
            </div>
          ) : (
            <div className="category-grid">
              {categories.map((c) => {
                const report = reports[c.id]
                const isOpen = openCategory === c.id
                return (
                  <button
                    key={c.id}
                    type="button"
                    className={`category-box ${isOpen ? 'category-box--active' : ''}`}
                    onClick={() => toggleCategory(c.id)}
                  >
                    <span className="category-box-label">{c.label}</span>
                    <span className="category-box-status">
                      {report?.loading
                        ? '取得中…'
                        : report?.error
                          ? '取得エラー'
                          : isOpen
                            ? '閉じる'
                            : 'レポートを見る'}
                    </span>
                  </button>
                )
              })}
            </div>
          )}

          {openCategory ? (
            <div className="market-report-panel">
              <div className="market-report-header">
                <h2>{openLabel}</h2>
                <button
                  type="button"
                  className="market-report-refresh"
                  onClick={() => void fetchReport(openCategory)}
                  disabled={openReport?.loading}
                  aria-label={`${openLabel}のレポートを再取得`}
                  title="再取得"
                >
                  <RefreshCw size={13} className={openReport?.loading ? 'spinning' : ''} />
                </button>
              </div>
              <MarketReport report={openReport} />
            </div>
          ) : null}
        </section>

        <aside className="market-fx-panel">
          <div className="market-fx-header">
            <h2>為替</h2>
            <button
              type="button"
              className="market-fx-refresh"
              onClick={() => void loadFx()}
              disabled={fxLoading}
              aria-label="為替情報を更新"
              title="更新"
            >
              <RefreshCw size={13} className={fxLoading ? 'spinning' : ''} />
            </button>
          </div>
          {fx.length === 0 && !fxLoading ? (
            <p className="market-fx-empty">為替情報を取得できませんでした</p>
          ) : (
            <ul className="market-fx-list">
              {fx.map((q) => {
                const up = (q.change_pct ?? 0) > 0
                const down = (q.change_pct ?? 0) < 0
                return (
                  <li key={q.symbol} className="market-fx-item">
                    <span className="market-fx-label">{q.label}</span>
                    <span className="market-fx-price">{fmtNum(q.price, 2)}</span>
                    <span
                      className={`market-fx-change ${up ? 'up' : down ? 'down' : ''}`}
                    >
                      {up ? (
                        <ArrowUpRight size={12} />
                      ) : down ? (
                        <ArrowDownRight size={12} />
                      ) : (
                        <Minus size={12} />
                      )}
                      {fmtPct(q.change_pct)}
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </aside>
      </div>

      <p className="screener-disclaimer">
        ※本情報は投資判断の参考であり、投資勧誘を目的としたものではありません。投資判断はご自身の責任で行ってください。
      </p>
    </main>
  )
}

function MarketReport({ report }: { report: CategoryReport | undefined }) {
  if (!report || (report.loading && !report.progress?.length)) {
    return (
      <div className="loading-bar">
        <span />
      </div>
    )
  }
  if (report.loading) {
    return <AgentProgress steps={report.progress ?? []} />
  }
  if (report.error) {
    return (
      <div className="market-report-error">
        <AlertCircle size={15} />
        <span>{report.error}</span>
      </div>
    )
  }
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
        {report.content ?? ''}
      </ReactMarkdown>
    </div>
  )
}
