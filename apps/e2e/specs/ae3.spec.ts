import { randomUUID } from 'node:crypto'

import { expect, test } from '../support/test.ts'

// AE3 (#355, point 3): Home's Closest to complete names what each set is missing, and either
// person can say a missing film does not count. Eastwood's Piano Blues, a TV documentary
// episode, set not to count moves the row on; Count it again brings it back. Both people see the
// same, at 375 px, in both themes.
test('AE3 Piano Blues set not to count moves Eastwood off the row, and Count it again restores it', async ({ signedIn, db }, testInfo) => {
  const owned = Number(db.scalar("SELECT tmdb_id FROM movies WHERE title = 'Copper Canyon' AND deleted_at IS NULL LIMIT 1"))
  expect(owned).toBeGreaterThan(0)
  const stamp = randomUUID().slice(0, 6)
  const eastwood = { id: randomUUID(), name: `AE3 Eastwood ${stamp}` }
  // Three sets two short, so Eastwood (one short) leads the row until Piano Blues stops counting.
  const others = [1, 2, 3].map((n) => ({ id: randomUUID(), name: `AE3 Other ${String(n)} ${stamp}`, members: [owned, 990_100 + n * 10, 990_101 + n * 10] }))
  const member = (tmdbId: number, title: string, year: number) => ({ tmdbId, title, year, posterPath: null })
  const insert = (id: string, name: string, members: number[], titles: { tmdbId: number; title: string; year: number; posterPath: null }[]) =>
    db.sql(`INSERT INTO completion_sets (id, set_type, set_key, set_name, member_tmdb_ids, metadata, last_refreshed)
      VALUES ('${id}', 'director', '${id}', '${name}', ARRAY[${members.join(',')}]::integer[],
        '${JSON.stringify({ members: titles })}'::jsonb, timezone('utc', now()))`)
  insert(eastwood.id, eastwood.name, [owned, 990_001], [member(990_001, 'Piano Blues', 2003)])
  for (const set of others) insert(set.id, set.name, set.members, [member(set.members[1], `Lost ${set.name}`, 1926), member(set.members[2], `Episode ${set.name}`, 1960)])
  try {
    for (const theme of ['light', 'dark'] as const) {
      // Mark says it does not count; Craig sees the same and undoes it.
      const mark = await signedIn('Mark')
      await mark.context.addInitScript((value) => localStorage.setItem('mcu-theme', value), theme)
      await mark.page.setViewportSize({ width: 375, height: 812 })
      await mark.page.goto('/dashboard')
      const row = mark.page.getByRole('region', { name: 'Closest to complete' })
      const missing = row.getByRole('list', { name: `Missing from ${eastwood.name}` })
      await expect(missing).toContainText('Piano Blues (2003)')
      // Wanted is Craig's to add to; Mark has Doesn't count.
      await expect(missing.getByRole('button', { name: 'Want' })).toHaveCount(0)
      await row.scrollIntoViewIfNeeded()
      await mark.page.screenshot({ path: testInfo.outputPath(`ae3-row-mark-${theme}-375.png`) })
      await missing.getByRole('button', { name: /Doesn’t count/ }).click()
      await expect(row.getByRole('list', { name: `Missing from ${eastwood.name}` })).toHaveCount(0)
      await expect(row.getByRole('list', { name: `Missing from ${others[2].name}` })).toBeVisible()
      expect(await mark.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)

      const craig = await signedIn('Craig')
      await craig.context.addInitScript((value) => localStorage.setItem('mcu-theme', value), theme)
      await craig.page.setViewportSize({ width: 375, height: 812 })
      await craig.page.goto('/insights')
      await craig.page.getByRole('button', { name: new RegExp(eastwood.name) }).first().click()
      const notCounted = craig.page.getByRole('region', { name: 'Not counted' })
      await expect(notCounted.getByText('Piano Blues (2003)')).toHaveCSS('text-decoration-line', 'line-through')
      await notCounted.scrollIntoViewIfNeeded()
      await craig.page.screenshot({ path: testInfo.outputPath(`ae3-set-craig-${theme}-375.png`) })
      await notCounted.getByRole('button', { name: /Count it again/ }).click()
      await expect(craig.page.getByRole('region', { name: 'Not counted' })).toHaveCount(0)

      await craig.page.goto('/dashboard')
      await expect(craig.page.getByRole('region', { name: 'Closest to complete' }).getByRole('list', { name: `Missing from ${eastwood.name}` })).toContainText('Piano Blues (2003)')
    }
    // Each change is audited: two not counted, two counted again.
    expect(db.scalar(`SELECT count(*) FROM admin_actions WHERE target_table = 'completion_exclusions' AND changes->>'setId' = '${eastwood.id}'`)).toBe('4')
  } finally {
    db.sql(`DELETE FROM completion_sets WHERE id IN ('${[eastwood.id, ...others.map((set) => set.id)].join("','")}')`)
  }
})
