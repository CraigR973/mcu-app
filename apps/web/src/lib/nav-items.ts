import type { LucideIcon } from 'lucide-react'
import { Bell, Bot, Boxes, Popcorn, CalendarDays, Film, Bookmark, Home, Store, LayoutDashboard, Plus, Settings2, ShieldCheck, HandHeart, ScrollText, Sparkle, Sparkles, Tag, Target, Trash2, TrendingUp } from 'lucide-react'

export interface NavItem {
  label: string
  path: string
  icon: LucideIcon
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

/** Not in the sidebar — it has no link there — but it is a real route, so the
 *  command palette's page index needs it named separately from `navItems`. */
export const HOME_ITEM: NavItem = { label: 'Archive shortcut', path: '/', icon: Home }

export const navItems: NavItem[] = [
  { label: 'Movies', path: '/movies', icon: Film },
  { label: 'Box sets', path: '/box-sets', icon: Boxes },
  { label: 'Collections', path: '/collections', icon: Sparkles },
  { label: 'Insights', path: '/insights', icon: Target },
  { label: 'Coming soon', path: '/discover', icon: Sparkle },
  { label: 'Calendar', path: '/calendar', icon: CalendarDays },
  { label: 'Wanted', path: '/wanted', icon: Bookmark },
  { label: 'Deals', path: '/deals', icon: Tag },
  { label: 'Home', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Stats', path: '/stats', icon: TrendingUp },
  { label: 'Loans', path: '/loans', icon: HandHeart },
  // Batch 35. Both people swipe, so it is an ordinary sidebar item.
  { label: 'Movie night', path: '/movie-night', icon: Popcorn },
  // Batch 11. Both people have their own devices and their own toggles, so this is a
  // sidebar item rather than an admin one.
  { label: 'Notifications', path: '/settings/notifications', icon: Bell },
  // Batch 31. The chat itself; Batch 30's caps and usage live under it at
  // /settings/ai, reachable from the header.
  { label: 'Assistant', path: '/assistant', icon: Bot },
  { label: 'AI settings', path: '/settings/ai', icon: Settings2 },
]

/** Batch 7's write surface. Admin-only, matching the routes and the API. */
export const adminNavItems: NavItem[] = [
  { label: 'Add a disc', path: '/collection/add', icon: Plus },
  { label: 'Trash', path: '/trash', icon: Trash2 },
  { label: 'Audit log', path: '/audit', icon: ScrollText },
  { label: 'Retailers', path: '/retailers', icon: Store },
  { label: 'Admin', path: '/admin', icon: ShieldCheck },
]

/**
 * The sidebar's information architecture. `navItems` stays flat because the command
 * palette searches destinations, while the shell groups them by the job somebody is
 * doing. This keeps all routes visible without presenting nineteen equal choices.
 */
export const navGroups: NavGroup[] = [
  { label: 'The archive', items: [navItems[0], navItems[6], navItems[1], navItems[2]] },
  { label: 'Plan a screening', items: [navItems[10], navItems[4], navItems[5]] },
  { label: 'Explore', items: [navItems[3], navItems[7], navItems[8], navItems[9]] },
  { label: 'Personal', items: [navItems[11], navItems[12], navItems[13]] },
]

export const adminNavGroup: NavGroup = {
  label: 'Administration',
  items: adminNavItems,
}
