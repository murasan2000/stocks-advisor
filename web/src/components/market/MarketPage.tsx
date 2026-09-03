import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  Calendar,
  Link2,
  Minus,
  Newspaper,
  RefreshCw,
  TrendingUp,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { AgentProgress } from '../chat/AgentProgress'
import type { CategoryReport, useMarket } from '../../hooks/useMarket'
import { fmtIsoDate, fmtNum, fmtPct, todayIso } from '../../utils/format'
import { ReportCalendar } from './ReportCalendar'

// レポート本文の先頭にある `# カテゴリ名` は market-report-header 側に既に
// 表示しているため二重表示を避けたい。ただし本文中に別の h1 が含まれる可能性
// （LLM生成テキストの自由度）まで一律に握りつぶさないよう、行頭の1つ目だけを
// 文字列として除去する（`^#\s` は `##` 以下の見出しにはマッチしない）。
function stripLeadingH1(markdown: string): string {
  return markdown.replace(/^#\s+[^\n]*\n+/, '')
}

// レポート本文の描画用。出典リンクは常に新しいタブで開く（issue #71: 埋め込み
// プレビューは埋め込み拒否サイトで表示事故が起きるため廃止）。
const REPORT_MARKDOWN_COMPONENTS = {
  h2: ({ children }: React.ComponentProps<'h2'>) => (
    <h2 className="report-heading">
      <Newspaper size={13} />
      <span>{children}</span>
    </h2>
  ),
  h4: ({ children }: React.ComponentProps<'h4'>) => (
    <h4 className="report-heading report-heading--sub">
      <Link2 size={12} />
      <span>{children}</span>
    </h4>
  ),
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
    viewingDate,
    calendarOpen,
    availableDates,
    reports,
    reportKey,
    loadFx,
    toggleCategory,
    toggleCalendar,
    viewDate,
    generateReport,
  } = market
  const openLabel = categories.find((c) => c.id === openCategory)?.label ?? ''
  const openReport =
    openCategory && viewingDate ? reports[reportKey(openCategory, viewingDate)] : undefined
  const isViewingToday = viewingDate === todayIso()

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
                // カテゴリボックスの状態表示は、開いている間は実際に表示中の日付の
                // 状態を、閉じている間は本日分の状態を反映する。
                const isOpen = openCategory === c.id
                const statusReport =
                  isOpen && viewingDate
                    ? reports[reportKey(c.id, viewingDate)]
                    : reports[reportKey(c.id, todayIso())]
                return (
                  <button
                    key={c.id}
                    type="button"
                    className={`category-box ${isOpen ? 'category-box--active' : ''}`}
                    onClick={() => void toggleCategory(c.id)}
                  >
                    <span className="category-box-label">{c.label}</span>
                    <span className="category-box-status">
                      {statusReport?.loading
                        ? '取得中…'
                        : statusReport?.error
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
                <div className="market-report-heading">
                  <h2>
                    <TrendingUp size={15} />
                    <span>{openLabel}</span>
                  </h2>
                  {viewingDate ? (
                    <span className="market-report-date">
                      {fmtIsoDate(viewingDate)}
                      {isViewingToday ? '（本日）' : ''}
                    </span>
                  ) : null}
                </div>
                <div className="market-report-actions">
                  <button
                    type="button"
                    className={`icon-btn ${calendarOpen ? 'icon-btn--active' : ''}`}
                    onClick={toggleCalendar}
                    aria-label="過去のレポートをカレンダーから選ぶ"
                    title="カレンダー"
                  >
                    <Calendar size={13} />
                  </button>
                  {isViewingToday ? (
                    <button
                      type="button"
                      className="icon-btn"
                      onClick={() => void generateReport(openCategory)}
                      disabled={openReport?.loading}
                      aria-label={`${openLabel}のレポートを再実行`}
                      title="再実行（本日分を上書き）"
                    >
                      <RefreshCw size={13} className={openReport?.loading ? 'spinning' : ''} />
                    </button>
                  ) : null}
                </div>
              </div>
              {calendarOpen ? (
                <ReportCalendar
                  availableDates={availableDates[openCategory] ?? []}
                  selectedDate={viewingDate}
                  onSelect={(date) => void viewDate(openCategory, date)}
                  onClose={toggleCalendar}
                />
              ) : null}
              <MarketReport report={openReport} />
            </div>
          ) : null}
        </section>

        <aside className="market-fx-panel">
          <div className="market-fx-header">
            <h2>為替</h2>
            <button
              type="button"
              className="icon-btn"
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
                    <span className={`market-fx-change ${up ? 'up' : down ? 'down' : ''}`}>
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
    <div className="md market-report-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={REPORT_MARKDOWN_COMPONENTS}>
        {stripLeadingH1(report.content ?? '')}
      </ReactMarkdown>
    </div>
  )
}
