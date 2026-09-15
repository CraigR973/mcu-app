import { Film, LayoutDashboard, Menu, Plus, Popcorn, Search } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'

import { cn } from '@/lib/utils'

interface MobileTabBarProps {
  onOpenMenu: () => void
  onOpenSearch: () => void
}

/* Six slots at 375px leaves ~62px each. `px-0.5` and a 9px label are what keep "Movie
   night" from truncating mid-word — measured in a browser at that width, not guessed. */
const TAB_CLS =
  'touch-target flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-md px-0.5 py-1 text-[0.5625rem] font-semibold leading-tight text-muted-foreground'

/**
 * Batch S3, snag 1: **search has a slot on every screen.** Batch S4, snag 7: **so does
 * adding a disc.**
 *
 * Search used to live in a second row of the mobile header — a permanent band of chrome
 * above every page, on the smallest screen, for a control most page views never use. Add
 * had no phone entry point at all: the header button is `hidden sm:inline-flex`, so below
 * 640px the app offered no way to add a disc from anywhere.
 *
 * **Wanted gave up its slot, and Add is the raised one.** Five slots for the things
 * somebody opens constantly — the Archive, a search of it, adding to it, Home, and a film
 * night — with "More" folded into Home's long-press territory. Wanted keeps its place in
 * the sidebar under "The archive", one tap further away.
 *
 * **Add is drawn as a filled circle rather than a fifth flat icon.** It is the only slot
 * here that *writes* anything, and at 375px five flat labels read as one undifferentiated
 * row; the accent is what makes it findable without a label long enough to truncate.
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
      className="safe-bottom fixed inset-x-0 bottom-0 z-30 grid grid-cols-6 border-t border-border bg-popover/96 px-1 pt-1.5 shadow-[0_-12px_35px_-28px_hsl(var(--shadow-colour)/0.65)] backdrop-blur-md lg:hidden"
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

      {/* Batch S4, snag 7. Visible below 640px, which is the whole point — the header's
          "Add a disc" is `hidden sm:inline-flex`, so this is the only add control a phone
          has. Not role-gated: `DECISIONS.md` #155 makes adding a viewer's to do, and every
          endpoint behind it moved in the same commit. */}
      <NavLink
        to="/collection/add"
        aria-label="Add a disc"
        className={({ isActive }) => cn(TAB_CLS, isActive && 'text-primary')}
      >
        <span className="flex h-[1.6rem] w-[1.6rem] items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Plus className="h-[1.05rem] w-[1.05rem]" aria-hidden />
        </span>
        <span className="max-w-full truncate">Add</span>
      </NavLink>

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
