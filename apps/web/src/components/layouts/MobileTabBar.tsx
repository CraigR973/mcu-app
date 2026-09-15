import { Film, LayoutDashboard, Menu, Popcorn, Search } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

import { cn } from '@/lib/utils'

interface MobileTabBarProps {
  onOpenMenu: () => void
  onOpenSearch: () => void
}

const TAB_CLS =
  'touch-target flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-md px-1 py-1 text-[0.625rem] font-semibold text-muted-foreground'

/**
 * Batch S3, snag 1: **search has a slot on every screen.**
 *
 * It used to live in a second row of the mobile header — a permanent band of chrome above
 * every page, on the smallest screen, for a control most page views never use. It is a
 * button here instead, one tap from anywhere, and the row is gone.
 *
 * **Wanted gave up its slot for it.** Five slots, and the bar is for the things somebody
 * opens constantly: the Archive, a search of it, Home, and a film night. Wanted keeps its
 * place in the sidebar under "The archive", one tap further away.
 */
const tabs = [
  { label: 'Archive', path: '/movies', icon: Film },
  { label: 'Home', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Movie night', path: '/movie-night', icon: Popcorn },
] as const

export function MobileTabBar({ onOpenMenu, onOpenSearch }: MobileTabBarProps) {
  const { pathname } = useLocation()
  const tabActive = tabs.some(({ path }) => pathname === path || pathname.startsWith(`${path}/`))

  return (
    <nav
      aria-label="Primary mobile navigation"
      className="safe-bottom fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-popover/96 px-1 pt-1.5 shadow-[0_-12px_35px_-28px_hsl(var(--shadow-colour)/0.65)] backdrop-blur-md lg:hidden"
    >
      <NavLink
        to={tabs[0].path}
        className={({ isActive }) => cn(TAB_CLS, isActive && 'bg-primary/10 text-primary')}
      >
        <Film className="h-[1.125rem] w-[1.125rem]" aria-hidden />
        <span className="max-w-full truncate">Archive</span>
      </NavLink>

      <button type="button" onClick={onOpenSearch} className={TAB_CLS} aria-label="Search the archive">
        <Search className="h-[1.125rem] w-[1.125rem]" aria-hidden />
        <span className="max-w-full truncate">Search</span>
      </button>

      {tabs.slice(1).map(({ label, path, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          className={({ isActive }) => cn(TAB_CLS, isActive && 'bg-primary/10 text-primary')}
        >
          <Icon className="h-[1.125rem] w-[1.125rem]" aria-hidden />
          <span className="max-w-full truncate">{label}</span>
        </NavLink>
      ))}

      <button
        type="button"
        onClick={onOpenMenu}
        className={cn(TAB_CLS, !tabActive && 'bg-primary/10 text-primary')}
        aria-label="Open all destinations"
      >
        <Menu className="h-[1.125rem] w-[1.125rem]" aria-hidden />
        <span>More</span>
      </button>
    </nav>
  )
}
