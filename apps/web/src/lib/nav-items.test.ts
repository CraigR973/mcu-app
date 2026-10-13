import { describe, expect, it } from 'vitest'
import type { NavSections } from '@mcu/shared'

import {
  adminNavItems,
  BOTTOM_BAR_PATHS,
  isTopLevel,
  isVisible,
  navGroups,
  navItems,
  parentPath,
  titleForPath,
  visibleGroups,
  YOU_ITEM,
} from './nav-items'

const EMPTY: NavSections = { boxSets: 0, collections: 0, deals: 0, loans: 0 }
const FULL: NavSections = { boxSets: 2, collections: 3, deals: 9, loans: 1 }

function labels(sections: NavSections | undefined): string[] {
  return visibleGroups(navGroups, sections).flatMap((group) => group.items.map((item) => item.label))
}

describe('the sidebar a signed-in non-admin sees', () => {
  it('is exactly eleven destinations while the two conditional tables are empty', () => {
    // **Batch S3 made this eight; Batch S6 made it seven**, by merging Calendar and
    // Coming soon into one Releases screen — its own criterion, and the same two-sources-
    // one-question argument `DECISIONS.md` #154 made about Home, Stats and Insights.
    // Fourteen → eight → seven. **Batch T8a made it eight again** with Price alerts,
    // which is always shown: it is where a first alert is set, so hiding it while empty
    // would hide the only way in (#218). **Batch V1 made it nine** with Loans, always
    // shown for Mark and Craig at Craig's word (#228): where a disc went is worth being
    // able to look up whether or not a loan has been made yet. **Batch X2 made it ten** with
    // Deals, always shown (#154 and #165 amended for Deals alone): hidden on empty, a blind
    // eBay scan looked the same as a quiet day. **Batch Y2 made it eleven** with Move discs,
    // always shown: either person moves discs (#264, #265).
    //
    // Asserted as the whole list rather than a count, so a swap that keeps the total
    // still fails.
    expect(labels(EMPTY)).toEqual([
      'Movies',
      'Move discs',
      'Wanted',
      'Movie night',
      'Releases',
      'Deals',
      'Price alerts',
      'Home',
      'Loans',
      'Assistant',
      'Settings',
    ])
  })

  it('grows to thirteen once both have rows — the un-hide half', () => {
    // **A hide that never un-hides is the failure mode.** It looks right on this
    // database, where all four tables are empty, and stays wrong forever.
    expect(labels(FULL)).toEqual([
      'Movies',
      'Move discs',
      'Wanted',
      'Box sets',
      'Collections',
      'Movie night',
      'Releases',
      'Deals',
      'Price alerts',
      'Home',
      'Loans',
      'Assistant',
      'Settings',
    ])
  })

  it('shows each destination independently, not all three together', () => {
    // The tables fill at different times — a first box set says nothing about deals —
    // so a single "is anything non-empty" flag would be wrong in both directions.
    expect(labels({ ...EMPTY, boxSets: 1 })).toContain('Box sets')
    expect(labels({ ...EMPTY, boxSets: 1 })).not.toContain('Collections')
    expect(labels({ ...EMPTY, collections: 4 })).toContain('Collections')
    expect(labels({ ...EMPTY, collections: 4 })).not.toContain('Box sets')
  })

  it('always lists Deals, with a deal on offer or none — Batch X2', () => {
    expect(labels({ ...EMPTY, deals: 0 })).toContain('Deals')
    expect(labels({ ...EMPTY, deals: 3 })).toContain('Deals')
    expect(navItems.find((item) => item.path === '/deals')?.showWhen).toBeUndefined()
  })

  it('always lists Loans, with no loan made yet or with one — Batch V1 (#228)', () => {
    // Loans hid itself while the table was empty from Batch S3 (#154) until V1.
    expect(labels({ ...EMPTY, loans: 0 })).toContain('Loans')
    expect(labels({ ...EMPTY, loans: 1 })).toContain('Loans')
    expect(navItems.find((item) => item.path === '/loans')?.showWhen).toBeUndefined()
  })

  it('shows everything when the counts have not arrived', () => {
    // The shell renders before `nav/sections` resolves, and offline it may never
    // resolve. Hiding four destinations because a request is slow would be a worse bug
    // than the emptiness this feature exists to fix.
    expect(labels(undefined)).toHaveLength(13)
  })

  it('drops a group heading left with no links under it', () => {
    // A heading over nothing is its own dead menu item — the exact thing #154 objects to.
    const groups = visibleGroups(
      [{ label: 'Only empties', items: navItems.filter((item) => item.showWhen) }],
      EMPTY,
    )
    expect(groups).toEqual([])
  })
})

describe('isVisible', () => {
  it('always shows a destination with no condition on it', () => {
    const movies = navItems.find((item) => item.path === '/movies')!
    expect(isVisible(movies, EMPTY)).toBe(true)
  })

  it('hides a conditional destination on exactly zero and no other value', () => {
    const collections = navItems.find((item) => item.path === '/collections')!
    expect(isVisible(collections, { ...EMPTY, collections: 0 })).toBe(false)
    expect(isVisible(collections, { ...EMPTY, collections: 1 })).toBe(true)
  })
})

describe('the destinations themselves', () => {
  it('has no Stats or Insights entry, because Home absorbed both', () => {
    const paths = navItems.map((item) => item.path)
    expect(paths).not.toContain('/stats')
    expect(paths).not.toContain('/insights')
  })

  it('has one Settings entry rather than a Notifications one and an AI one', () => {
    const paths = navItems.map((item) => item.path)
    expect(paths).toContain('/settings')
    expect(paths).not.toContain('/settings/notifications')
    expect(paths).not.toContain('/settings/ai')
  })

  it('places every destination in a group', () => {
    // AI settings was defined here and placed in no group before Batch S3, which is how
    // it became reachable only from a header button. Grouping is now total by assertion.
    const grouped = new Set(navGroups.flatMap((group) => group.items.map((item) => item.path)))
    expect(navItems.filter((item) => !grouped.has(item.path))).toEqual([])
  })

  it('puts Export in the admin menu, not the ordinary one', () => {
    expect(adminNavItems.map((item) => item.path)).toContain('/export')
    expect(navItems.map((item) => item.path)).not.toContain('/export')
  })
})

describe('Batch S4 — quick add within reach', () => {
  it('keeps Add a disc in the admin menu while the page itself is open to a viewer', () => {
    // `DECISIONS.md` #155 widens *reach*, and the sidebar's Administration group is still
    // Craig's own list. What changed is the route guard and the API behind it — the page
    // is reachable by a viewer from Home and from the bottom bar, which is where snag 7
    // said a phone had nothing at all.
    expect(adminNavItems.map((item) => item.path)).toContain('/collection/add')
  })

  it('leaves the four admin-only tools where they are', () => {
    // A batch about widening access is exactly when a boundary quietly stops being
    // enforced, so the four that do not move are named here as well as in the API tests.
    const admin = adminNavItems.map((item) => item.path)
    for (const path of ['/trash', '/audit', '/retailers', '/admin']) {
      expect(admin).toContain(path)
      expect(navItems.map((item) => item.path)).not.toContain(path)
    }
  })
})

describe('Batch T3 — the phone top bar', () => {
  it('names a destination by its menu label, and a page below one by what it shows', () => {
    expect(titleForPath('/wanted')).toBe('Wanted')
    expect(titleForPath('/you')).toBe('You')
    expect(titleForPath('/movies/3f2504e0-4f89-11d3-9a0c-0305e82c3301')).toBe('Film')
    expect(titleForPath('/films/tmdb/11050')).toBe('Film')
    expect(titleForPath('/movie-night/3f2504e0-4f89-11d3-9a0c-0305e82c3301')).toBe('Movie night')
    expect(titleForPath('/nowhere')).toBeNull()
  })

  it("names Your eBay, which has no menu entry, and sends it back to Settings — Batch T8b", () => {
    expect(titleForPath('/ebay')).toBe('Your eBay')
    expect(isTopLevel('/ebay')).toBe(false)
    expect(parentPath('/ebay')).toBe('/settings')
    // eBay's two return addresses sit below Settings, so they take its name and go back to it.
    expect(titleForPath('/settings/ebay/connected')).toBe('Settings')
    expect(parentPath('/settings/ebay/declined')).toBe('/settings')
  })

  it('gives a back arrow to every page but the four bottom tabs and You — Batch V1', () => {
    // Until V1 every menu destination counted as top-level, so Wanted, Deals, Settings and
    // the rest had no arrow on a phone though the only way to them was through You (snag 5).
    const topLevel = new Set<string>([...BOTTOM_BAR_PATHS, YOU_ITEM.path])
    for (const path of topLevel) expect(isTopLevel(path), path).toBe(true)
    for (const path of [...navItems, ...adminNavItems].map((item) => item.path)) {
      expect(isTopLevel(path), path).toBe(topLevel.has(path))
    }
    for (const path of ['/wanted', '/deals', '/settings', '/loans', '/calendar', '/admin']) {
      expect(isTopLevel(path), path).toBe(false)
    }
    expect(isTopLevel('/movies/abc')).toBe(false)
    expect(isTopLevel('/films/tmdb/1')).toBe(false)
    expect(isTopLevel('/settings/ai')).toBe(false)
  })

  it('sends a page with no history to You when You lists it, and to its parent otherwise', () => {
    // Opened from a notification or a link, a page You lists goes where it would have been
    // opened from; a page below a destination goes to that destination.
    for (const path of ['/wanted', '/deals', '/settings', '/loans', '/price-alerts', '/retailers']) {
      expect(parentPath(path), path).toBe('/you')
    }
    expect(parentPath('/movies/abc')).toBe('/movies')
    expect(parentPath('/movie-night/abc')).toBe('/movie-night')
    expect(parentPath('/films/tmdb/1')).toBe('/movies')
    expect(parentPath('/box-sets/abc')).toBe('/box-sets')
    expect(parentPath('/somewhere/else')).toBe('/dashboard')
  })

  it('never sends a bottom-tab page to You, since You does not list one', () => {
    for (const path of BOTTOM_BAR_PATHS) expect(parentPath(path), path).not.toBe('/you')
  })

  it('keeps four destinations in the bottom bar, every one a real page', () => {
    const known = new Set([...navItems, ...adminNavItems].map((item) => item.path))
    expect([...BOTTOM_BAR_PATHS]).toEqual(['/dashboard', '/movies', '/collection/add', '/movie-night'])
    for (const path of BOTTOM_BAR_PATHS) expect(known.has(path), path).toBe(true)
  })
})

