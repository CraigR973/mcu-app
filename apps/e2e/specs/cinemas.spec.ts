import { randomUUID } from 'node:crypto'
import type { Page } from '@playwright/test'
import { test as base, expect } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const json = (value: unknown) => `${sql(JSON.stringify(value))}::jsonb`
type Venue = { id: string; source: string; programme_url: string; collection_enabled: boolean }
type Programme = { day: string; title: string; prefix: string; domainCounts: string }

// This fixture only uses the harness's guarded, disposable Postgres. The page's programme
// response is never intercepted: grouping, coverage, categories and personal watch status
// must come from the real authenticated API reading these rows.
const test = base.extend<{ programme: Programme }>({
  programme: async ({ db }, use) => {
    const prefix = `ab7:${randomUUID()}`
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value
    const day = new Date(Date.parse(`${part('year')}-${part('month')}-${part('day')}T12:00:00Z`) + 86400000).toISOString().slice(0, 10)
    const movie = JSON.parse(db.scalar(`SELECT json_build_object('id',m.id,'title',m.title,'year',m.year,'tmdb_id',m.tmdb_id)::text FROM movies m WHERE m.deleted_at IS NULL AND NOT m.is_tv AND EXISTS (SELECT FROM collection_items c WHERE c.movie_id=m.id AND c.deleted_at IS NULL AND c.listing_status IN ('in_collection','listed_for_sale')) AND NOT EXISTS (SELECT FROM watch_log w WHERE w.movie_id=m.id AND w.deleted_at IS NULL) ORDER BY m.title LIMIT 1`)) as { id: string; title: string; year: number | null; tmdb_id: number | null }
    const venues = JSON.parse(db.scalar(`SELECT json_agg(v)::text FROM cinema_venues v WHERE slug IN ('vue-st-enoch','odeon-kilmarnock')`)) as Venue[]
    expect(venues).toHaveLength(2)
    const watch = randomUUID()
    const coverageIds = venues.map(() => randomUUID())
    db.sql(`INSERT INTO watch_log (id,movie_id,user_id,watched_at,is_rewatch) SELECT ${sql(watch)},${sql(movie.id)},id,CURRENT_DATE,false FROM profiles WHERE display_name='Craig'`)
    for (const [index, venue] of venues.entries()) {
      db.sql(`UPDATE cinema_venues SET collection_enabled=true WHERE id=${sql(venue.id)};
        INSERT INTO cinema_coverage (id,venue_id,local_date,status,observed,complete,last_attempt_utc,last_success_utc) VALUES (${sql(coverageIds[index])},${sql(venue.id)},${sql(day)},'partial',true,false,now() AT TIME ZONE 'utc',now() AT TIME ZONE 'utc')`)
    }
    for (let index = 0; index < 5; index++) {
      const venue = venues[index === 1 ? 1 : 0]
      const film = randomUUID()
      const older = index < 2
      const category = older ? 'olderFilm' : index === 2 ? 'newRelease' : 'unclassified'
      const evidence = category === 'unclassified' ? {} : { sourceUrl: venue.programme_url, quote: older ? 'Anniversary screening' : 'First UK theatrical run', run: older ? 'returning' : 'firstUkTheatrical', reissue: older }
      const title = older ? movie.title : index === 2 ? 'A current first run' : 'Programme identity pending'
      const booking = venue.source === 'vue' ? 'https://www.myvue.com/book-tickets/fixture' : 'https://www.odeon.co.uk/ticketing/seat-picker/fixture'
      db.sql(`INSERT INTO cinema_films (id,source,source_key,title,movie_id,original_year,identity_status,evidence) VALUES (${sql(film)},${sql(venue.source)},${sql(`${prefix}:${index}`)},${sql(title)},${older ? sql(movie.id) : 'NULL'},${older && movie.year !== null ? movie.year : 'NULL'},${sql(index < 3 ? 'verified' : 'unverified')},${json(older && movie.tmdb_id ? { tmdbId: movie.tmdb_id } : {})});
        INSERT INTO cinema_screenings (id,venue_id,film_id,source_key,identity_strength,local_date,source_local_start,starts_utc,formats,booking_url,release_category,category_evidence,confirmation) VALUES (${sql(randomUUID())},${sql(venue.id)},${sql(film)},${sql(`${prefix}:${index}`)},'opaque',${sql(day)},${sql(`${day}T${18 + index}:00:00Z`)},${sql(`${day}T${18 + index}:00:00`)},'["2D"]'::jsonb,${sql(booking)},${sql(category)},${json(evidence)},'confirmed')`)
    }
    const countQuery = `SELECT json_build_array((SELECT count(*) FROM movies),(SELECT count(*) FROM collection_items),(SELECT count(*) FROM watch_log),(SELECT count(*) FROM cinema_screenings),(SELECT count(*) FROM cinema_refresh_runs))`
    const domainCounts = db.scalar(countQuery)
    try {
      await use({ day, title: movie.title, prefix, domainCounts })
      expect(db.scalar(countQuery), 'browsing must not change catalogue, diary or programme rows').toBe(domainCounts)
    } finally {
      db.sql(`DELETE FROM cinema_films WHERE source_key LIKE ${sql(`${prefix}:%`)}; DELETE FROM cinema_coverage WHERE id IN (${coverageIds.map(sql).join(',')}); DELETE FROM watch_log WHERE id=${sql(watch)}`)
      for (const venue of venues) db.sql(`UPDATE cinema_venues SET collection_enabled=${venue.collection_enabled} WHERE id=${sql(venue.id)}`)
    }
  },
})

async function selectDay(page: Page, day: string) {
  // Set the upper bound first so a tomorrow selection never passes through an inverted range.
  await page.getByLabel('To date').fill(day)
  await page.getByLabel('From date').fill(day)
  await expect(page.getByRole('option', { name: 'All films (5 screenings)' })).toBeAttached()
}

for (const person of ['Craig', 'Mark'] as const) {
  test(`cinemas keeps ${person}'s watched status and returning films in both phone themes`, async ({ signedIn, programme }, testInfo) => {
    const { context, page } = await signedIn(person)
    await page.setViewportSize({ width: 375, height: 844 })
    for (const theme of ['light', 'dark']) {
      await context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
      await page.goto('/cinemas')
      await selectDay(page, programme.day)
      const favourite = page.getByRole('article', { name: programme.title, exact: true })
      await expect(favourite).toContainText(person === 'Craig' ? 'You have watched this' : 'You have not watched this')
      await expect(favourite.getByRole('link', { name: 'Check tickets' })).toHaveCount(2)
      await expect(favourite).toContainText('Vue Glasgow St Enoch')
      await expect(favourite).toContainText('ODEON Kilmarnock')
      await expect(page.getByRole('article', { name: 'Programme identity pending', exact: true })).toHaveCount(2)
      await expect(page.getByRole('option', { name: 'New releases (1 screening)' })).toBeAttached()
      await page.getByLabel('Release category').selectOption('olderFilm')
      await expect(page.getByRole('article')).toHaveCount(1)
      await expect(favourite).toBeVisible()
      await expect(page.getByRole('option', { name: 'Unclassified (2 screenings)' })).toBeAttached()
      await expect(page.getByText('Partial coverage:', { exact: false })).toBeVisible()
      for (const link of await favourite.getByRole('link', { name: 'Check tickets' }).all()) {
        await expect(link).toHaveAttribute('target', '_blank')
        await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
        await expect(link).toHaveAttribute('referrerpolicy', 'no-referrer')
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`cinemas-${person.toLowerCase()}-${theme}-375.png`) })
      await favourite.scrollIntoViewIfNeeded()
      await page.screenshot({ path: testInfo.outputPath(`cinemas-${person.toLowerCase()}-${theme}-film-375.png`) })
    }
  })
}

test('cinemas retains failed and unconfirmed showings without advertising ticket checks', async ({ signedIn, db, programme }) => {
  db.sql(`UPDATE cinema_coverage SET status='failed',error='Fixture source refused the latest check' WHERE local_date=${sql(programme.day)} AND venue_id IN (SELECT id FROM cinema_venues WHERE slug='vue-st-enoch'); UPDATE cinema_screenings SET confirmation='unconfirmed' WHERE source_key LIKE ${sql(`${programme.prefix}:%`)}`)
  const { page } = await signedIn('Craig')
  await page.goto('/cinemas'); await selectDay(page, programme.day)
  await expect(page.getByRole('link', { name: 'Check tickets' })).toHaveCount(0)
  await expect(page.getByText('Showing unconfirmed', { exact: false })).toHaveCount(5)
  await page.getByText('Coverage and sources', { exact: true }).click()
  await expect(page.getByRole('region', { name: 'Vue Glasgow St Enoch coverage' }).getByText(`${programme.day} · Latest check failed`, { exact: true })).toBeVisible()
  await expect(page.getByText('Fixture source refused the latest check')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Official programme', exact: true })).toHaveCount(14)
})

test('cinemas pauses cached ticket checks immediately offline and retains official fallbacks', async ({ signedIn, programme }) => {
  const { context, page } = await signedIn('Mark')
  await page.goto('/cinemas'); await selectDay(page, programme.day)
  await expect(page.getByRole('link', { name: 'Check tickets' })).toHaveCount(5)
  await context.setOffline(true)
  await expect(page.getByText('Offline · saved programme only.', { exact: false })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Check tickets' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Official programme', exact: true })).toHaveCount(5)
  await context.setOffline(false)
})

test('cinemas is reachable from Home and mobile You while retaining five bottom tabs', async ({ signedIn, programme }) => {
  const { page } = await signedIn('Mark')
  await page.setViewportSize({ width: 375, height: 844 })
  await page.goto('/dashboard')
  await page.getByRole('link', { name: 'At the cinema', exact: true }).click()
  await expect(page).toHaveURL(/\/cinemas$/)
  await selectDay(page, programme.day)
  const tabs = page.getByRole('navigation', { name: 'Primary mobile navigation' })
  await expect(tabs.getByRole('link')).toHaveCount(4)
  await expect(tabs.getByRole('button', { name: 'Search the archive' })).toHaveCount(1)
  await page.getByRole('link', { name: 'You: every other page, and your account' }).click()
  await page.getByRole('link', { name: 'Cinemas', exact: true }).click()
  await expect(page).toHaveURL(/\/cinemas$/)
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto('/dashboard')
  await page.getByRole('navigation', { name: 'Application destinations' }).getByRole('link', { name: 'Cinemas', exact: true }).focus()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/cinemas$/)
  await page.goto('/dashboard')
  await expect(page.getByRole('navigation', { name: 'Application destinations' }).getByRole('link', { name: 'Cinemas', exact: true })).toBeVisible()
  await page.keyboard.press('Control+k')
  const palette = page.getByRole('textbox', { name: 'Command palette', exact: true })
  await palette.fill('Cinemas')
  await expect(page.getByRole('option', { name: 'Cinemas', exact: true })).toBeVisible()
  await palette.press('Enter')
  await expect(page).toHaveURL(/\/cinemas$/)
})

test('cinemas requires an authenticated profile', async ({ page }) => {
  await page.goto('/cinemas')
  await expect(page).toHaveURL(/\/login$/)
})
