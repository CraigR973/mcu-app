import { NavLink } from 'react-router-dom'
import { Film, Bookmark, LayoutDashboard, ShieldCheck, X } from 'lucide-react'
import { useAuth } from '@/context/auth'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface Props {
  open: boolean
  onClose: () => void
}

const navItems = [
  { label: 'Movies', path: '/movies', icon: Film },
  { label: 'Watchlist', path: '/watchlist', icon: Bookmark },
  { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
]

export default function Sidebar({ open, onClose }: Props) {
  const { user, profile, signOut } = useAuth()

  return (
    <>
      {/* Backdrop (mobile) */}
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-card border-r border-border transition-transform duration-200',
          'lg:relative lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-border">
          <span className="font-bold text-foreground tracking-tight">The Real MCU</span>
          <button className="lg:hidden text-muted-foreground hover:text-foreground" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 space-y-1 px-2">
          {navItems.map(({ label, path, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}

          {profile?.role === 'admin' && (
            <NavLink
              to="/admin"
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                )
              }
            >
              <ShieldCheck size={16} />
              Admin
            </NavLink>
          )}
        </nav>

        {/* Footer */}
        <div className="border-t border-border px-4 py-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground truncate max-w-[140px]">{user?.email}</span>
            <ThemeToggle />
          </div>
          <Button variant="ghost" size="sm" className="w-full justify-start text-muted-foreground" onClick={signOut}>
            Sign out
          </Button>
        </div>
      </aside>
    </>
  )
}
