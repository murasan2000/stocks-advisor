import {
  Bookmark,
  Briefcase,
  LineChart,
  Settings,
  SlidersHorizontal,
} from 'lucide-react'
import type { View } from '../App'

interface NavItem {
  view: View
  icon: React.ReactNode
  label: string
}

const NAV_ITEMS: NavItem[] = [
  { view: 'screener', icon: <SlidersHorizontal size={18} />, label: 'スクリーニング' },
  { view: 'watchlist', icon: <Bookmark size={18} />, label: 'ウォッチリスト' },
  { view: 'portfolio', icon: <Briefcase size={18} />, label: '保有銘柄' },
  { view: 'market', icon: <LineChart size={18} />, label: 'マーケット' },
]

const DISABLED_ITEMS = [{ icon: <Settings size={18} />, label: '設定' }]

interface Props {
  view: View
  onChangeView: (view: View) => void
}

export function Sidebar({ view, onChangeView }: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="sidebar-logo-mark">📈</span>
        <span className="sidebar-logo-text">
          Stocks<span className="sidebar-accent">Advisor</span>
        </span>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.label}
            className={`sidebar-nav-item ${
              view === item.view ? 'sidebar-nav-item--active' : ''
            }`}
            onClick={() => onChangeView(item.view)}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
        {DISABLED_ITEMS.map((item) => (
          <button
            key={item.label}
            className="sidebar-nav-item"
            disabled
            title="近日公開"
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-avatar">U</div>
          <div className="sidebar-user-info">
            <div className="sidebar-user-name">Userさん</div>
            <div className="sidebar-user-role">投資家</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
