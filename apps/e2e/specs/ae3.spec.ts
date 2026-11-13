import { randomUUID } from 'node:crypto'

import { expect, test } from '../support/test.ts'

// AE3 (#355, point 3): Home's Closest to complete names what each set is missing, and either
// person can say a missing film does not count. Eastwood's Piano Blues, a TV documentary
// episode, set not to count moves the row on; Count it again brings it back. Both people see the
// same, at 375 px, in both themes. AF2 (#372): Home names the films and has no buttons; a set's
// page lists its missing films with Want and Doesn't count side by side, nothing overlapping at
// 320, 375 or 390 px.
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
      const set = row.getByRole('button', { name: new RegExp(eastwood.name) })
      await expect(set).toContainText('Missing: Piano Blues (2003)')
      // AF2: one block per set and nothing else to press on Home.
      await expect(row.getByRole('button')).toHaveCount(3)
      await row.scrollIntoViewIfNeeded()
      await mark.page.screenshot({ path: testInfo.outputPath(`ae3-row-mark-${theme}-375.png`) })
      await set.click()
      // Wanted is Craig's to add to; Mark has Doesn't count, on the set's page.
      const film = mark.page.getByRole('region', { name: 'Missing films' }).getByRole('listitem', { name: 'Piano Blues' })
      await expect(film).toContainText('Piano Blues (2003)')
      await expect(film.getByRole('button', { name: 'Add to Wanted' })).toHaveCount(0)
      await film.getByRole('button', { name: /Doesn’t count/ }).click()
      await expect(mark.page.getByRole('region', { name: 'Not counted' })).toContainText('Piano Blues (2003)')
      await mark.page.getByRole('button', { name: 'Home', exact: true }).click()
      await expect(row.getByRole('button', { name: new RegExp(eastwood.name) })).toHaveCount(0)
      await expect(row.getByRole('button', { name: new RegExp(others[2].name) })).toBeVisible()
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

      // AF2: Craig's Want and Doesn't count sit side by side in the film's row, each wholly inside
      // it and neither on the other, from the narrowest phone up.
      const piano = craig.page.getByRole('region', { name: 'Missing films' }).getByRole('listitem', { name: 'Piano Blues' })
      for (const width of [320, 375, 390]) {
        await craig.page.setViewportSize({ width, height: 812 })
        const want = piano.getByRole('button', { name: 'Add to Wanted' })
        const doesNotCount = piano.getByRole('button', { name: /Doesn’t count/ })
        await expect(want).toBeVisible()
        await expect(doesNotCount).toBeVisible()
        const [rowBox, wantBox, countBox] = await Promise.all([piano.boundingBox(), want.boundingBox(), doesNotCount.boundingBox()])
        if (!rowBox || !wantBox || !countBox) throw new Error('A row or button has no box')
        for (const box of [wantBox, countBox]) {
          expect(box.x).toBeGreaterThanOrEqual(rowBox.x - 0.5)
          expect(box.x + box.width).toBeLessThanOrEqual(rowBox.x + rowBox.width + 0.5)
        }
        const apart = wantBox.x + wantBox.width <= countBox.x + 0.5 || countBox.x + countBox.width <= wantBox.x + 0.5
          || wantBox.y + wantBox.height <= countBox.y + 0.5 || countBox.y + countBox.height <= wantBox.y + 0.5
        expect(apart).toBe(true)
        expect(await craig.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        await piano.scrollIntoViewIfNeeded()
        await craig.page.screenshot({ path: testInfo.outputPath(`ae3-missing-craig-${theme}-${String(width)}.png`) })
      }
      await craig.page.setViewportSize({ width: 375, height: 812 })

      await craig.page.goto('/dashboard')
      await expect(craig.page.getByRole('region', { name: 'Closest to complete' }).getByRole('button', { name: new RegExp(eastwood.name) })).toContainText('Missing: Piano Blues (2003)')
    }
    // Each change is audited: two not counted, two counted again.
    expect(db.scalar(`SELECT count(*) FROM admin_actions WHERE target_table = 'completion_exclusions' AND changes->>'setId' = '${eastwood.id}'`)).toBe('4')
  } finally {
    db.sql(`DELETE FROM completion_sets WHERE id IN ('${[eastwood.id, ...others.map((set) => set.id)].join("','")}')`)
  }
})
