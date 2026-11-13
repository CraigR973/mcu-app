import { randomUUID } from 'node:crypto'

import type { Locator } from '@playwright/test'

import { expect, test } from '../support/test.ts'

// AF4 (#372, snag 4): Back returns you to where you had scrolled. The app scrolls inside its own
// panel, and the Archive's grid in a box of its own, so the browser's own restore never applied.
// Each case scrolls well down, opens something, comes back by a different way back (the phone's
// arrow, the browser's Back, the page's own button), and finds the same place; a page newly
// opened starts at the top.

const MAIN = '#main-content'

async function scrollTo(box: Locator, top: number): Promise<number> {
  await box.evaluate((element, to) => { element.scrollTop = to }, top)
  // A virtual grid redraws as it scrolls; read the place once it has settled.
  await expect.poll(() => box.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
  return box.evaluate(element => element.scrollTop)
}

/** The first film whose middle is inside what the box shows, so the case taps a film it can see,
 *  by its middle, without Playwright scrolling anything first. */
async function linkInView(box: Locator): Promise<{ href: string; x: number; y: number }> {
  const area = await box.boundingBox()
  if (!area) throw new Error('The scroll box has no box')
  for (const link of await box.getByRole('link').all()) {
    const at = await link.boundingBox()
    const middle = at ? at.y + at.height / 2 : -1
    if (!at || middle < area.y + 8 || middle > area.y + area.height - 8) continue
    const href = await link.getAttribute('href')
    if (href) return { href, x: at.x + at.width / 2, y: at.y + at.height / 2 }
  }
  throw new Error('No film wholly in view')
}

test('AF4 Back from a film puts the Archive grid where it was, and the film opens at the top', async ({ signedIn }, testInfo) => {
  const { page } = await signedIn('Craig')
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/movies')
  const grid = page.locator('[data-scroll-memory="archive-grid"]')
  await expect(grid.getByRole('link').first()).toBeVisible()
  const before = await scrollTo(grid, 1400)
  const film = await linkInView(grid)
  await page.mouse.click(film.x, film.y)
  await expect(page).toHaveURL(new RegExp(`${film.href}$`))
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  // A page newly opened starts at the top, not at the grid's place.
  expect(await page.locator(MAIN).evaluate(element => element.scrollTop)).toBe(0)

  // The phone's back arrow goes back through history.
  await page.getByRole('banner', { name: 'Top bar' }).getByRole('button', { name: 'Back' }).click()
  await expect(page).toHaveURL(/\/movies$/)
  await expect.poll(() => grid.evaluate(element => element.scrollTop)).toBeGreaterThanOrEqual(before - 2)
  expect(await grid.evaluate(element => element.scrollTop)).toBeLessThanOrEqual(before + 2)
  expect((await linkInView(grid)).href).toBe(film.href)
  await page.screenshot({ path: testInfo.outputPath('af4-archive-back-375.png') })
})

test('AF4 a completion set opened from Home goes back to where Home was', async ({ signedIn, db }, testInfo) => {
  // A set for Home's Closest to complete, as AE3 makes them: one film on the shelf, one missing.
  const owned = Number(db.scalar("SELECT tmdb_id FROM movies WHERE title = 'Copper Canyon' AND deleted_at IS NULL LIMIT 1"))
  const id = randomUUID()
  db.sql(`INSERT INTO completion_sets (id, set_type, set_key, set_name, member_tmdb_ids, metadata, last_refreshed)
    VALUES ('${id}', 'director', '${id}', 'AF4 Director ${id.slice(0, 6)}', ARRAY[${String(owned)}, 990901]::integer[],
      '${JSON.stringify({ members: [{ tmdbId: 990901, title: 'AF4 Missing Film', year: 1999, posterPath: null }] })}'::jsonb, timezone('utc', now()))`)
  try {
    const { page } = await signedIn('Craig')
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/dashboard')
    const row = page.getByRole('region', { name: 'Closest to complete' })
    const set = row.getByRole('button').first()
    await set.scrollIntoViewIfNeeded()
    const main = page.locator(MAIN)
    // Where the reader is as they tap: the click itself scrolls nothing now.
    const before = await main.evaluate(element => element.scrollTop)
    expect(before).toBeGreaterThan(200)
    await set.click()
    await expect(page.getByRole('button', { name: 'Home', exact: true })).toBeVisible()
    // The set opens at its top, not partway down.
    expect(await main.evaluate(element => element.scrollTop)).toBe(0)
    await page.getByRole('button', { name: 'Home', exact: true }).click()
    await expect(row).toBeVisible()
    await expect.poll(() => main.evaluate(element => element.scrollTop)).toBeGreaterThanOrEqual(before - 2)
    expect(await main.evaluate(element => element.scrollTop)).toBeLessThanOrEqual(before + 2)
    await page.screenshot({ path: testInfo.outputPath('af4-home-set-back-375.png') })
  } finally {
    db.sql(`DELETE FROM completion_sets WHERE id = '${id}'`)
  }
})
