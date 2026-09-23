import type { LucideIcon } from 'lucide-react'
import { Bot, Boxes, Download, Popcorn, CalendarDays, Film, Bookmark, Home, Store, LayoutDashboard, Plus, Settings2, ShieldCheck, HandHeart, ScrollText, Sparkles, Tag, Trash2, UserRound } from 'lucide-react'

import type { NavSections } from '@mcu/shared'

export interface NavItem {
  label: string
  path: string
  icon: LucideIcon
  /**
   * Which `nav/sections` count decides whether this item is shown.
   *
   * Absent means "always shown". Present means **hidden while that count is 0** and
   * visible the moment it is not — `DECISIONS.md` #154. Measured on 2026-09-14, all four
   * of these tables held zero rows, so five of fourteen destinations led to a page with
   * nothing on it.
   */
  showWhen?: keyof NavSections
}

export interface NavGroup {
  label: string
  items: NavItem[]
}

/** Not in the sidebar — it has no link there — but it is a real route, so the
 *  command palette's page index needs it named separately from `navItems`. */
export const HOME_ITEM: NavItem = { label: 'Archive shortcut', path: '/', icon: Home }

/**
 * Every non-admin destination, flat, because the command palette searches destinations
 * while the shell groups them by the job somebody is doing.
 *
 * **Batch S3 took this from fifteen defined entries to nine, by two different means**,
 * because the menu had two different problems (`DECISIONS.md` #154):
 *
 * - **Merged what was thin but real.** Home, Stats and Insights are one reading page at
 *   `/dashboard`; Notifications and AI settings are one `/settings` page. Four items
 *   become two, and `/settings/ai` stops being a destination reachable only from the
 *   header — it was defined here but placed in no group at all.
 * - **Hid what is empty.** Box sets, Collections, Deals and Loans carry `showWhen` and
 *   stay out of the menu until their table has a row.
 *
 * With all four empty — the state of the database today — **a signed-in non-admin sees
 * eight destinations**, down from fourteen.
 */
export const navItems: NavItem[] = [
  { label: 'Movies', path: '/movies', icon: Film },
  { label: 'Box sets', path: '/box-sets', icon: Boxes, showWhen: 'boxSets' },
  { label: 'Collections', path: '/collections', icon: Sparkles, showWhen: 'collections' },
  // Batch S6: one destination, because the two pages answered the same question from two
  // sources. `/discover` redirects here.
  { label: 'Releases', path: '/calendar', icon: CalendarDays },
  { label: 'Wanted', path: '/wanted', icon: Bookmark },
  { label: 'Deals', path: '/deals', icon: Tag, showWhen: 'deals' },
  // Batch S3: Home now *is* Stats and Insights. `/stats` and `/insights` redirect here
  // rather than 404, because they are in people's history and in the command palette.
  { label: 'Home', path: '/dashboard', icon: LayoutDashboard },
  { label: 'Loans', path: '/loans', icon: HandHeart, showWhen: 'loans' },
  // Batch 35. Both people swipe, so it is an ordinary sidebar item.
  { label: 'Movie night', path: '/movie-night', icon: Popcorn },
  // Batch 31. The chat itself.
  { label: 'Assistant', path: '/assistant', icon: Bot },
  // Batch S3. Notifications + AI settings, one page. AI settings was defined as a
  // destination before this batch and sat in no group — reachable only from the header.
  { label: 'Settings', path: '/settings', icon: Settings2 },
]

/** Batch 7's write surface. Admin-only, matching the routes and the API. */
export const adminNavItems: NavItem[] = [
  { label: 'Add a disc', path: '/collection/add', icon: Plus },
  { label: 'Trash', path: '/trash', icon: Trash2 },
  { label: 'Audit log', path: '/audit', icon: ScrollText },
  { label: 'Retailers', path: '/retailers', icon: Store },
  // Batch S3. Moved here from the foot of the old Stats page.
  { label: 'Export', path: '/export', icon: Download },
  { label: 'Admin', path: '/admin', icon: ShieldCheck },
]

/**
 * The sidebar's information architecture.
 *
 * Built by name rather than by index. The previous version indexed into `navItems`
 * (`navItems[10]`, `navItems[13]`) so **removing one entry silently re-pointed three
 * groups at the wrong destinations** — and adding one left `AI settings` in no group at
 * all, which is how it ended up reachable only from the header. A lookup by path cannot
 * drift that way, and `byPath` throws rather than rendering a hole.
 */
function byPath(path: string): NavItem {
  const item = navItems.find((candidate) => candidate.path === path)
  if (!item) throw new Error(`nav-items: no destination at ${path}`)
  return item
}

export const navGroups: NavGroup[] = [
  {
    label: 'The archive',
    items: [byPath('/movies'), byPath('/wanted'), byPath('/box-sets'), byPath('/collections')],
  },
  {
    label: 'Plan a screening',
    items: [byPath('/movie-night'), byPath('/calendar')],
  },
  { label: 'Explore', items: [byPath('/deals'), byPath('/dashboard'), byPath('/loans')] },
  { label: 'Personal', items: [byPath('/assistant'), byPath('/settings')] },
]

export const adminNavGroup: NavGroup = {
  label: 'Administration',
  items: adminNavItems,
}

/**
 * Whether a destination should appear, given what the API says is behind it.
 *
 * **`undefined` counts as "show".** The shell renders before `nav/sections` resolves, and
 * on a cold or offline load it may never resolve — hiding four destinations because a
 * count has not arrived yet would make the menu flicker, and hiding them permanently
 * because the request failed would be worse than the emptiness this feature is fixing.
 * So an unknown count shows the item; only a count that is genuinely `0` hides it.
 */
export function isVisible(item: NavItem, sections: NavSections | undefined): boolean {
  if (!item.showWhen) return true
  if (!sections) return true
  return sections[item.showWhen] > 0
}

/** The groups with their empty destinations removed, and any group left with nothing in
 *  it dropped entirely — a heading over no links is its own kind of dead menu item. */
export function visibleGroups(
  groups: NavGroup[],
  sections: NavSections | undefined,
): NavGroup[] {
  return groups
    .map((group) => ({ ...group, items: group.items.filter((item) => isVisible(item, sections)) }))
    .filter((group) => group.items.length > 0)
}

// ---------------------------------------------------------------------------
// Batch T3 — five tabs, a title in the top bar, and a "You" page
// ---------------------------------------------------------------------------

/** Everything that is not in the bottom bar lives on this page — `DECISIONS.md` #201. */
export const YOU_ITEM: NavItem = { label: 'You', path: '/you', icon: UserRound }

/**
 * The destinations the phone's bottom bar carries, in its order. Search is the fifth slot,
 * and is a button rather than a page. The "You" page lists everything *not* here.
 */
export const BOTTOM_BAR_PATHS = ['/dashboard', '/movies', '/collection/add', '/movie-night'] as const

const TOP_LEVEL_PATHS = new Set<string>([
  '/',
  YOU_ITEM.path,
  ...navItems.map(({ path }) => path),
  ...adminNavItems.map(({ path }) => path),
])

/** Pages below a destination, named by what they show rather than where they sit. */
const SUB_PAGE_TITLES: Array<[prefix: string, title: string]> = [
  ['/movies/', 'Film'],
  ['/films/tmdb/', 'Film'],
  ['/movie-night/', 'Movie night'],
  ['/box-sets/', 'Box set'],
  ['/collections/', 'Collection'],
  ['/settings/', 'Settings'],
]

/** A destination's own page, as opposed to something opened from it. Sub-pages get a
 *  back arrow in the top bar; destinations do not. */
export function isTopLevel(pathname: string): boolean {
  return TOP_LEVEL_PATHS.has(pathname)
}

/** What the phone's top bar calls this page when the page itself has not said. */
export function titleForPath(pathname: string): string | null {
  const exact = [...navItems, ...adminNavItems, YOU_ITEM].find(({ path }) => path === pathname)
  if (exact) return exact.label
  const sub = SUB_PAGE_TITLES.find(([prefix]) => pathname.startsWith(prefix))
  if (sub) return sub[1]
  const parent = [...navItems, ...adminNavItems]
    .filter(({ path }) => pathname.startsWith(`${path}/`))
    .sort((a, b) => b.path.length - a.path.length)[0]
  return parent?.label ?? null
}

/** Where the back arrow goes when there is no history to go back through — a page opened
 *  from a notification or a shared link. */
export function parentPath(pathname: string): string {
  if (pathname.startsWith('/films/')) return '/movies'
  const parent = [...navItems, ...adminNavItems]
    .filter(({ path }) => pathname.startsWith(`${path}/`))
    .sort((a, b) => b.path.length - a.path.length)[0]
  return parent?.path ?? '/dashboard'
}
