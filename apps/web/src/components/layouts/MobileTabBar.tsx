import { Bookmark, Film, LayoutDashboard, Menu, Popcorn } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

import { cn } from '@/lib/utils'

interface MobileTabBarProps {
  onOpenMenu: () => void
}

const tabs = [
  { label: 'Archive', path: '/movies', icon: Film },
  { label: 'Wanted', path: '/wanted', icon: Bookmark },
  { label: 'Movie night', path: '/movie-night', icon: Popcorn },
  { label: 'Home', path: '/dashboard', icon: LayoutDashboard },
] as const

export function MobileTabBar({ onOpenMenu }: MobileTabBarProps) {
  const { pathname } = useLocation()
  const tabActive = tabs.some(({ path }) => pathname === path || pathname.startsWith(`${path}/`))

  return (
    <nav
      aria-label="Primary mobile navigation"
      className="safe-bottom fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-popover/96 px-1 pt-1.5 shadow-[0_-12px_35px_-28px_hsl(var(--shadow-colour)/0.65)] backdrop-blur-md lg:hidden"
    >
      {tabs.map(({ label, path, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          className={({ isActive }) =>
            cn(
              'touch-target flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-md px-1 py-1 text-[0.625rem] font-semibold text-muted-foreground',
              isActive && 'bg-primary/10 text-primary',
            )
          }
        >
          <Icon className="h-[1.125rem] w-[1.125rem]" aria-hidden />
          <span className="max-w-full truncate">{label}</span>
        </NavLink>
      ))}
      <button
        type="button"
        onClick={onOpenMenu}
        className={cn(
          'touch-target flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-md px-1 py-1 text-[0.625rem] font-semibold text-muted-foreground',
          !tabActive && 'bg-primary/10 text-primary',
        )}
        aria-label="Open all destinations"
      >
        <Menu className="h-[1.125rem] w-[1.125rem]" aria-hidden />
        <span>More</span>
      </button>
    </nav>
  )
}
