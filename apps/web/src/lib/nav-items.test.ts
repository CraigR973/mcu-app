import { describe, expect, it } from 'vitest'
import type { NavSections } from '@mcu/shared'

import { adminNavItems, isVisible, navGroups, navItems, visibleGroups } from './nav-items'

const EMPTY: NavSections = { boxSets: 0, collections: 0, deals: 0, loans: 0 }
const FULL: NavSections = { boxSets: 2, collections: 3, deals: 9, loans: 1 }

function labels(sections: NavSections | undefined): string[] {
  return visibleGroups(navGroups, sections).flatMap((group) => group.items.map((item) => item.label))
}

describe('the sidebar a signed-in non-admin sees', () => {
  it('is exactly seven destinations while the four conditional tables are empty', () => {
    // **Batch S3 made this eight; Batch S6 made it seven**, by merging Calendar and
    // Coming soon into one Releases screen — its own criterion, and the same two-sources-
    // one-question argument `DECISIONS.md` #154 made about Home, Stats and Insights.
    // Fourteen → eight → seven.
    //
    // Asserted as the whole list rather than a count, so a swap that keeps the total
    // still fails.
    expect(labels(EMPTY)).toEqual([
      'Movies',
      'Wanted',
      'Movie night',
      'Releases',
      'Home',
      'Assistant',
      'Settings',
    ])
  })

  it('grows to eleven once all four have rows — the un-hide half', () => {
    // **A hide that never un-hides is the failure mode.** It looks right on this
    // database, where all four tables are empty, and stays wrong forever.
    expect(labels(FULL)).toEqual([
      'Movies',
      'Wanted',
      'Box sets',
      'Collections',
      'Movie night',
      'Releases',
      'Deals',
      'Home',
      'Loans',
      'Assistant',
      'Settings',
    ])
  })

  it('shows each destination independently, not all four together', () => {
    // The tables fill at different times — a first box set says nothing about loans —
    // so a single "is anything non-empty" flag would be wrong in both directions.
    expect(labels({ ...EMPTY, loans: 1 })).toContain('Loans')
    expect(labels({ ...EMPTY, loans: 1 })).not.toContain('Deals')
    expect(labels({ ...EMPTY, deals: 4 })).toContain('Deals')
    expect(labels({ ...EMPTY, deals: 4 })).not.toContain('Box sets')
  })

  it('shows everything when the counts have not arrived', () => {
    // The shell renders before `nav/sections` resolves, and offline it may never
    // resolve. Hiding four destinations because a request is slow would be a worse bug
    // than the emptiness this feature exists to fix.
    expect(labels(undefined)).toHaveLength(11)
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
    const deals = navItems.find((item) => item.path === '/deals')!
    expect(isVisible(deals, { ...EMPTY, deals: 0 })).toBe(false)
    expect(isVisible(deals, { ...EMPTY, deals: 1 })).toBe(true)
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
