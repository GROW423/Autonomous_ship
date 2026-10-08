import { ReactNode, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Ship, Map, LogOut, User, Users, MapPin, Shield, Menu, X, Home } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const isAdmin = user?.role === 'admin' || user?.is_admin

  const navItems = [
    { path: '/boats', label: '我的船', icon: Ship },
    { path: '/map', label: '地图总览', icon: Map },
  ]

  const adminNavItems = [
    { path: '/admin/users', label: '用户管理', icon: Users },
    { path: '/admin/regions', label: '区域管理', icon: MapPin },
  ]

  const roleLabel = user?.role === 'admin' ? '总管理员' : user?.role === 'regional_admin' ? '地方管理员' : '普通用户'

  // 底部导航项（手机端）
  const bottomNavItems = [
    { path: '/boats', label: '我的船', icon: Ship },
    ...(isAdmin ? [{ path: '/admin/users', label: '管理', icon: Users }] : []),
  ]

  const renderNavLink = (item: any, onClick?: () => void) => {
    const Icon = item.icon
    const active = location.pathname.startsWith(item.path)
    return (
      <Link
        key={item.path}
        to={item.path}
        onClick={onClick}
        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${
          active ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-700'
        }`}
      >
        <Icon className="w-5 h-5 flex-shrink-0" />
        <span className="text-sm">{item.label}</span>
      </Link>
    )
  }

  return (
    <div className="flex h-screen bg-gray-100">
      {/* 桌面端侧边栏 (md以上显示) */}
      <aside className="hidden md:flex w-56 lg:w-60 bg-slate-800 text-white flex-col">
        <div className="p-4 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <Ship className="w-6 h-6 text-blue-400" />
            <span className="font-bold text-lg">无人船控制</span>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map((item) => renderNavLink(item))}
          {isAdmin && (
            <>
              <div className="pt-4 pb-1 px-3">
                <span className="text-xs text-slate-500 uppercase tracking-wider">系统管理</span>
              </div>
              {adminNavItems.map((item) => renderNavLink(item))}
            </>
          )}
        </nav>

        <div className="p-3 border-t border-slate-700">
          <div className="flex items-center gap-2 mb-3 px-2">
            <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0">
              <User className="w-4 h-4" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{user?.username}</div>
              <div className="text-xs text-slate-400 flex items-center gap-1">
                <Shield className="w-3 h-3" />
                {roleLabel}
              </div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-slate-300 hover:bg-slate-700 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            <span className="text-sm">退出登录</span>
          </button>
        </div>
      </aside>

      {/* 手机端抽屉菜单 */}
      {mobileMenuOpen && (
        <div className="md:hidden fixed inset-0 z-50">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileMenuOpen(false)} />
          <aside className="absolute left-0 top-0 bottom-0 w-64 bg-slate-800 text-white flex flex-col animate-slide-in">
            <div className="p-4 border-b border-slate-700 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Ship className="w-6 h-6 text-blue-400" />
                <span className="font-bold text-lg">无人船控制</span>
              </div>
              <button onClick={() => setMobileMenuOpen(false)} className="p-1 hover:bg-slate-700 rounded">
                <X className="w-5 h-5" />
              </button>
            </div>
            <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
              {navItems.map((item) => renderNavLink(item, () => setMobileMenuOpen(false)))}
              {isAdmin && (
                <>
                  <div className="pt-4 pb-1 px-3">
                    <span className="text-xs text-slate-500 uppercase tracking-wider">系统管理</span>
                  </div>
                  {adminNavItems.map((item) => renderNavLink(item, () => setMobileMenuOpen(false)))}
                </>
              )}
            </nav>
            <div className="p-3 border-t border-slate-700">
              <div className="flex items-center gap-2 mb-3 px-2">
                <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center">
                  <User className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{user?.username}</div>
                  <div className="text-xs text-slate-400">{roleLabel}</div>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-slate-300 hover:bg-slate-700 transition-colors"
              >
                <LogOut className="w-4 h-4" />
                <span className="text-sm">退出登录</span>
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 手机端顶部栏 */}
        <header className="md:hidden bg-slate-800 text-white px-4 py-3 flex items-center justify-between flex-shrink-0">
          <button onClick={() => setMobileMenuOpen(true)} className="p-1 hover:bg-slate-700 rounded">
            <Menu className="w-6 h-6" />
          </button>
          <div className="flex items-center gap-2">
            <Ship className="w-5 h-5 text-blue-400" />
            <span className="font-bold">无人船控制</span>
          </div>
          <div className="w-8" />
        </header>

        {/* 内容区域 */}
        <main className="flex-1 overflow-auto pb-16 md:pb-0">{children}</main>

        {/* 手机端底部导航 */}
        <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-slate-800 text-white flex justify-around items-center py-2 border-t border-slate-700 z-40">
          {bottomNavItems.map((item) => {
            const Icon = item.icon
            const active = location.pathname.startsWith(item.path)
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex flex-col items-center gap-0.5 px-4 py-1 rounded-lg transition-colors ${
                  active ? 'text-blue-400' : 'text-slate-400'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span className="text-xs">{item.label}</span>
              </Link>
            )
          })}
          <Link
            to="/boats"
            className={`flex flex-col items-center gap-0.5 px-4 py-1 rounded-lg transition-colors ${
              location.pathname === '/boats' ? 'text-blue-400' : 'text-slate-400'
            }`}
          >
            <Home className="w-5 h-5" />
            <span className="text-xs">首页</span>
          </Link>
        </nav>
      </div>
    </div>
  )
}
