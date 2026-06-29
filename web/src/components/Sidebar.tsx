import { BarChart2, Home, MessageSquare, Settings } from 'lucide-react'

interface NavItem {
  icon: React.ReactNode
  label: string
  active?: boolean
}

const NAV_ITEMS: NavItem[] = [
  { icon: <Home size={18} />, label: 'ホーム' },
  { icon: <MessageSquare size={18} />, label: 'チャット', active: true },
  { icon: <BarChart2 size={18} />, label: 'ポートフォリオ' },
  { icon: <Settings size={18} />, label: '設定' },
]

export function Sidebar() {
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
            className={`sidebar-nav-item ${item.active ? 'sidebar-nav-item--active' : ''}`}
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
