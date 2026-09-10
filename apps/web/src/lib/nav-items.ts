import type { LucideIcon } from 'lucide-react'
import { Bell, Bot, Boxes, CalendarDays, Film, Bookmark, Gift, Home, Store, LayoutDashboard, Plus, ShieldCheck, HandHeart, ScrollText, Sparkle, Sparkles, Target, Trash2, TrendingUp } from 'lucide-react'

export interface NavItem {
  label: string
  path: string
  icon: LucideIcon
}

/** Not in the sidebar — it has no link there — but it is a real route, so the
 *  command palette's page index needs it named separately from `navItems`. */
export const HOME_ITEM: NavItem = { label: 'Home', path: '/', icon: Home }

export const navItems: NavItem[] = [
  { label: 'Movies', path: '/movies', icon: Film },
  { label: 'Box sets', path: '/box-sets', icon: Boxes },
  { label: 'Collections', path: '/collections', icon: Sparkles },
  { label: 'Insights', path: '/insights', icon: Target },
  { label: 'Coming soon', path: '/discover', icon: Sparkle },
  { label: 'Calendar', path: '/calendar', icon: CalendarDays },
  { label: 'Wanted', path: '/wanted', icon: Bookmark },
  { label: 'Dashboard', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Stats', path: '/stats', icon: TrendingUp },
  { label: 'Loans', path: '/loans', icon: HandHeart },
  // Batch 11. Both people have their own devices and their own toggles, so this is a
  // sidebar item rather than an admin one.
  { label: 'Notifications', path: '/settings/notifications', icon: Bell },
  // Batch 30. Per-person caps and usage; Batch 31 turns this into the chat.
  { label: 'Assistant', path: '/settings/ai', icon: Bot },
]

/** Batch 7's write surface. Admin-only, matching the routes and the API. */
export const adminNavItems: NavItem[] = [
  { label: 'Add a disc', path: '/collection/add', icon: Plus },
  { label: 'Trash', path: '/trash', icon: Trash2 },
  { label: 'Audit log', path: '/audit', icon: ScrollText },
  { label: 'Retailers', path: '/retailers', icon: Store },
  { label: 'Gift links', path: '/gift-links', icon: Gift },
  { label: 'Admin', path: '/admin', icon: ShieldCheck },
]
