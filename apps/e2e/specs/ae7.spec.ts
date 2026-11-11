import { randomUUID } from 'node:crypto'
import { test as base, expect } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`

// AE7 (#355): the top bar's search finds what was meant through a typo, a missing accent or a
// missing hyphen, against the real API on Postgres with migration 077's trigrams and folding.
// Two owned films join the imported shelf for the accent and the hyphen; rows go only into the
// harness's disposable Postgres.
const test = base.extend<{ shelf: void }>({
  shelf: async ({ db }, use) => {
    const films = [
      { id: randomUUID(), title: 'Amélie', year: 2001 },
      { id: randomUUID(), title: 'Spider-Man', year: 2002 },
    ]
    db.sql(films.map(film => `INSERT INTO movies (id,title,original_title,year,media_type) VALUES (${sql(film.id)},${sql(film.title)},${sql(film.title)},${String(film.year)},'film');
      INSERT INTO collection_items (id,movie_id,formats,location,condition) VALUES (${sql(randomUUID())},${sql(film.id)},'["blu_ray"]'::jsonb,'Lounge','good');`).join('\n'))
    const ids = films.map(film => sql(film.id)).join(',')
    try {
      await use()
    } finally {
      // A plain DELETE on collection_items only moves a copy to the Trash (migration 013's
      // trigger), so the films would stay referenced: remove both for good, as AD1's spec does,
      // and leave nothing behind for the next case's counts.
      db.sql(`BEGIN; SET LOCAL app.permanent_delete = 'on';
        DELETE FROM collection_items WHERE movie_id IN (${ids});
        DELETE FROM movies WHERE id IN (${ids}); COMMIT`)
      expect(db.scalar(`SELECT count(*) FROM movies WHERE id IN (${ids})`)).toBe('0')
    }
  },
})

for (const [typed, meant] of [
  ['quiet engin', 'The Quiet Engine'],
  ['lighthous keepr', 'The Lighthouse Keeper'],
  ['amelie', 'Amélie'],
  ['spiderman', 'Spider-Man'],
] as const) {
  test(`AE7 the top bar finds ${meant} from "${typed}"`, async ({ signedIn, shelf }) => {
    void shelf // its films are on the shelf
    const { page } = await signedIn('Craig')
    await page.goto('/dashboard')
    await page.getByRole('combobox', { name: 'Search films' }).fill(typed)
    await expect(page.getByRole('option').first()).toContainText(meant)
  })
}

test('AE7 a typo finds the film at 375 px, in both themes', async ({ signedIn, shelf }, testInfo) => {
  void shelf
  for (const theme of ['light', 'dark'] as const) {
    const { context, page } = await signedIn('Mark')
    await page.setViewportSize({ width: 375, height: 812 })
    await context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
    await page.goto('/dashboard')
    await page.getByRole('button', { name: 'Search the archive' }).click()
    const box = page.getByRole('combobox', { name: 'Search films' })
    await box.fill('quiet engin')
    await expect(page.getByRole('option').first()).toContainText('The Quiet Engine')
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`ae7-typo-mark-${theme}-375.png`) })
    await page.getByRole('option').first().click()
    await expect(page).toHaveURL(/\/movies\/[0-9a-f-]{36}$/)
    await expect(page.getByRole('heading', { name: /The Quiet Engine/ }).first()).toBeVisible()
    await context.close()
  }
})
