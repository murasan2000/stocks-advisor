import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { dateToIso, todayIso } from '../../utils/format'

const WEEKDAYS = ['日', '月', '火', '水', '木', '金', '土']

interface Props {
  availableDates: string[] // レポートが保存されている日付（YYYY-MM-DD）
  selectedDate: string | null
  onSelect: (date: string) => void
}

/** カテゴリ×日付で永続化されたレポートを振り返るための月表示カレンダー（issue #66）。
 * レポートが存在しない過去日・未来日は非活性にする。本日は未生成でも常に選択可能
 * （選ぶとAI生成のフォールバックに繋がる、呼び出し側 useMarket.viewDate の責務）。 */
export function ReportCalendar({ availableDates, selectedDate, onSelect }: Props) {
  const today = todayIso()
  const now = new Date()
  const initial = selectedDate ? new Date(`${selectedDate}T00:00:00`) : now
  const [viewYear, setViewYear] = useState(initial.getFullYear())
  const [viewMonth, setViewMonth] = useState(initial.getMonth()) // 0-indexed

  const available = new Set(availableDates)
  const firstWeekday = new Date(viewYear, viewMonth, 1).getDay()
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()
  const cells: (number | null)[] = [
    ...Array<null>(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ]

  const isCurrentOrFutureMonth =
    viewYear > now.getFullYear() ||
    (viewYear === now.getFullYear() && viewMonth >= now.getMonth())

  const goPrevMonth = () => {
    if (viewMonth === 0) {
      setViewYear((y) => y - 1)
      setViewMonth(11)
    } else {
      setViewMonth((m) => m - 1)
    }
  }
  const goNextMonth = () => {
    if (isCurrentOrFutureMonth) return
    if (viewMonth === 11) {
      setViewYear((y) => y + 1)
      setViewMonth(0)
    } else {
      setViewMonth((m) => m + 1)
    }
  }

  return (
    <div className="report-calendar">
      <div className="report-calendar-header">
        <button type="button" className="icon-btn" onClick={goPrevMonth} aria-label="前の月">
          <ChevronLeft size={14} />
        </button>
        <span>
          {viewYear}年{viewMonth + 1}月
        </span>
        <button
          type="button"
          className="icon-btn"
          onClick={goNextMonth}
          disabled={isCurrentOrFutureMonth}
          aria-label="次の月"
        >
          <ChevronRight size={14} />
        </button>
      </div>
      <div className="report-calendar-weekdays">
        {WEEKDAYS.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className="report-calendar-grid">
        {cells.map((day, i) => {
          if (day === null) {
            return <span key={`empty-${i}`} className="report-calendar-cell report-calendar-cell--empty" />
          }
          const iso = dateToIso(new Date(viewYear, viewMonth, day))
          const isToday = iso === today
          const hasData = available.has(iso)
          const disabled = !isToday && !hasData
          const isSelected = iso === selectedDate
          return (
            <button
              key={iso}
              type="button"
              className={[
                'report-calendar-cell',
                isSelected ? 'report-calendar-cell--selected' : '',
                isToday ? 'report-calendar-cell--today' : '',
                hasData ? 'report-calendar-cell--has-data' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              disabled={disabled}
              onClick={() => onSelect(iso)}
            >
              {day}
            </button>
          )
        })}
      </div>
    </div>
  )
}
