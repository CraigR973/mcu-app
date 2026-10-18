import { Film, LayoutDashboard, Plus, Popcorn, Search } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { cn } from '@/lib/utils'

interface MobileTabBarProps {
  onOpenSearch: () => void
}

/* Five slots at 375px leave 75px each, which fits "Movie night" at 12px — the smallest
   size this bar may use (Batch X12b raised it from 11px; the slot's side padding and the
   label's tracking went to keep it whole). Batch S3's six slots needed a 9px label to fit. */
const TAB_CLS =
  'touch-target flex min-w-0 flex-col items-center justify-center gap-0.5 rounded-md px-0 py-1 text-xs font-semibold leading-tight tracking-tight text-muted-foreground'

const ICON_CLS = 'h-5 w-5'

/**
 * The phone's bottom bar — Batch T3, `DECISIONS.md` #201.
 *
 * **Five slots: Home · Archive · Add · Movie night · Search.** Batch S3 and S4 built six,
 * with a "More" slot that opened the same slide-out menu as the top bar's menu button.
 * Six slots forced 9px labels, and two buttons opened one menu. Everything that is not
 * here now lives on the "You" page, opened from the person's initial in the top bar.
 *
 * **Search keeps its slot**, as Craig asked on 14 Sep, and **Add stays the raised one**:
 * it is the only slot that writes anything.
 */
export function MobileTabBar({ onOpenSearch }: MobileTabBarProps) {
  const link = ({ isActive }: { isActive: boolean }) => cn(TAB_CLS, isActive && 'bg-primary/10 text-primary')

  return (
    <nav
      aria-label="Primary mobile navigation"
      className="safe-bottom fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-popover/96 px-0 pt-1.5 shadow-[0_-12px_35px_-28px_hsl(var(--shadow-colour)/0.65)] backdrop-blur-md lg:hidden"
    >
      <NavLink to="/dashboard" className={link}>
        <LayoutDashboard className={ICON_CLS} aria-hidden />
        <span className="max-w-full truncate">Home</span>
      </NavLink>

      <NavLink to="/movies" className={link}>
        <Film className={ICON_CLS} aria-hidden />
        <span className="max-w-full truncate">Archive</span>
      </NavLink>

      {/* Batch S4, snag 7. The only add control a phone has — the header's "Add a disc" is
          `hidden sm:inline-flex`. Not role-gated: `DECISIONS.md` #155. */}
      <NavLink
        to="/collection/add"
        aria-label="Add a disc"
        className={({ isActive }) => cn(TAB_CLS, isActive && 'text-primary')}
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-primary-foreground">
          <Plus className="h-[1.1rem] w-[1.1rem]" aria-hidden />
        </span>
        <span className="max-w-full truncate">Add</span>
      </NavLink>

      <NavLink to="/movie-night" className={link}>
        <Popcorn className={ICON_CLS} aria-hidden />
        <span className="max-w-full truncate">Movie night</span>
      </NavLink>

      <button type="button" onClick={onOpenSearch} className={TAB_CLS} aria-label="Search the archive">
        <Search className={ICON_CLS} aria-hidden />
        <span className="max-w-full truncate">Search</span>
      </button>
    </nav>
  )
}
