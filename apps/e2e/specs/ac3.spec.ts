import { randomUUID } from 'node:crypto'
import type { Page } from '@playwright/test'
import { test as base, expect } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const json = (value: unknown) => `${sql(JSON.stringify(value))}::jsonb`
type Fixture = { day: string; linked: string; waiting: string }

// AC3 (#335): a linked film's run shows its stored reason, and a film the rule could not settle
// waits for Craig's check on Identify films. Rows go only into the harness's disposable Postgres,
// and the pages read them through the real API; the decision is the real POST.
const test = base.extend<{ ac3: Fixture }>({
  ac3: async ({ db }, use) => {
    const prefix = `ac3:${randomUUID()}`
    const tag = prefix.slice(4, 12)
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value
    const day = new Date(Date.parse(`${part('year')}-${part('month')}-${part('day')}T12:00:00Z`) + 86400000).toISOString().slice(0, 10)
    const venue = JSON.parse(db.scalar(`SELECT json_build_object('id',id,'source',source,'enabled',collection_enabled)::text FROM cinema_venues WHERE slug='vue-st-enoch'`)) as { id: string; source: string; enabled: boolean }
    const coverage = randomUUID()
    db.sql(`UPDATE cinema_venues SET collection_enabled=true WHERE id=${sql(venue.id)};
      INSERT INTO cinema_coverage (id,venue_id,local_date,status,observed,complete,last_attempt_utc,last_success_utc) VALUES (${sql(coverage)},${sql(venue.id)},${sql(day)},'partial',true,false,now() AT TIME ZONE 'utc',now() AT TIME ZONE 'utc')`)
    const linked = `A linked rerun ${tag}`
    const waiting = `A film to check ${tag}`
    // A 1976 film TMDB dates to a 1977 UK release, and a namesake with no facts at all. Their
    // ids are no film in the seeded collection, so neither link borrows a collection title.
    const original = { tmdb_id: 9_000_011, title: waiting, original_title: waiting, primary_release_date: '1976-11-21', gb_theatrical: [{ date: '1977-03-31', type: 3 }], vote_count: 7000 }
    const namesake = { tmdb_id: 9_000_012, title: waiting, original_title: waiting, vote_count: 1 }
    const rows = [
      { title: linked, status: 'verified', evidence: { tmdbId: 9_000_013, identity: { outcome: 'linked', reason: '', corroboration: ['the director'], others: [] } }, category: 'olderFilm', run: { run: 'rerun', runReason: 'UK release 1977 · rerun' } },
      {
        title: waiting,
        status: 'review',
        evidence: {
          metadata: { source: venue.source, film_key: `${prefix}:1`, fingerprint: 'a'.repeat(64), fetched_utc: '2026-11-05T08:00:00', state: 'candidate', candidates: [original, namesake] },
          identity: { outcome: 'review', reason: 'the title matches, but nothing else agrees', corroboration: [], others: [9_000_011, 9_000_012] },
        },
        category: 'unclassified',
        run: {},
      },
    ]
    for (const [index, row] of rows.entries()) {
      const film = randomUUID()
      db.sql(`INSERT INTO cinema_films (id,source,source_key,title,identity_status,evidence) VALUES (${sql(film)},${sql(venue.source)},${sql(`${prefix}:${index}`)},${sql(row.title)},${sql(row.status)},${json(row.evidence)});
        INSERT INTO cinema_screenings (id,venue_id,film_id,source_key,identity_strength,local_date,source_local_start,starts_utc,formats,booking_url,release_category,category_evidence,confirmation) VALUES (${sql(randomUUID())},${sql(venue.id)},${sql(film)},${sql(`${prefix}:${index}`)},'opaque',${sql(day)},${sql(`${day}T${19 + index}:00:00Z`)},${sql(`${day}T${19 + index}:00:00`)},'[]'::jsonb,'https://www.myvue.com/book-tickets/fixture',${sql(row.category)},${json(row.run)},'confirmed')`)
    }
    try {
      await use({ day, linked, waiting })
    } finally {
      db.sql(`DELETE FROM cinema_films WHERE source_key LIKE ${sql(`${prefix}:%`)}; DELETE FROM cinema_coverage WHERE id=${sql(coverage)};
        UPDATE cinema_venues SET collection_enabled=${venue.enabled} WHERE id=${sql(venue.id)}`)
    }
  },
})

// AC4: AC3's cinema states, through At the cinema and a film's page.
async function openDay(page: Page, day: string) {
  await page.goto(`/movie-night/cinema?day=${day}`)
  await expect(page.getByRole('region', { name: 'At the cinema' })).toBeVisible()
}

test('Craig sees why a showing is a rerun, settles a film the rule could not, and the programme follows', async ({ signedIn, ac3 }, testInfo) => {
  const { page } = await signedIn('Craig')
  await page.setViewportSize({ width: 375, height: 844 })
  await openDay(page, ac3.day)
  const linked = page.getByRole('article', { name: ac3.linked, exact: true })
  await expect(linked).toContainText('Rerun')
  const waiting = page.getByRole('article', { name: ac3.waiting, exact: true })
  await expect(waiting).toContainText('Waiting for a check')
  await page.screenshot({ path: testInfo.outputPath('ac3-cinemas-craig-375.png') })
  // The run's reason is on the film's page, by each showing.
  await linked.getByRole('link').click()
  await expect(page.getByRole('heading', { name: ac3.linked, level: 1 })).toBeVisible()
  await expect(page.getByText('UK release 1977 · rerun', { exact: true })).toBeVisible()
  await page.goBack()

  await page.getByRole('article', { name: ac3.waiting, exact: true }).getByRole('link', { name: 'Check which film this is' }).click()
  await expect(page).toHaveURL(/\/identify$/)
  const card = page.getByRole('article', { name: ac3.waiting, exact: true })
  await expect(card).toContainText('the title matches, but nothing else agrees')
  await expect(card.getByRole('list', { name: `Films offered for ${ac3.waiting}` }).getByRole('listitem')).toHaveCount(2)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('ac3-identify-craig-375.png') })
  await card.getByRole('button', { name: /This is it/ }).first().click()
  await expect(card).toHaveCount(0)

  // Settled, it is a film: one card with its run, and its page gives the reason.
  await openDay(page, ac3.day)
  const settled = page.getByRole('region', { name: /^\w{3} \d+ \w{3}$/ }).getByRole('article', { name: ac3.waiting, exact: true })
  await expect(settled).toContainText('Rerun')
  await expect(page.getByRole('region', { name: 'Not matched to a film yet' }).getByRole('article', { name: ac3.waiting, exact: true })).toHaveCount(0)
  await settled.getByRole('link').click()
  await expect(page.getByRole('heading', { name: ac3.waiting, level: 1 })).toBeVisible()
  await expect(page.getByText('UK release 1977 · rerun', { exact: true })).toBeVisible()
  await expect(page.getByText('Identity waiting for a check', { exact: false })).toHaveCount(0)
})

test('Mark sees a film waiting for a check, but not the check', async ({ signedIn, ac3 }) => {
  const { page } = await signedIn('Mark')
  await page.setViewportSize({ width: 375, height: 844 })
  await openDay(page, ac3.day)
  const waiting = page.getByRole('article', { name: ac3.waiting, exact: true })
  await expect(waiting).toContainText('Waiting for a check')
  await expect(waiting.getByRole('link', { name: 'Check which film this is' })).toHaveCount(0)
  await waiting.getByRole('link').first().click()
  const check = page.getByRole('region', { name: 'Which film this is' })
  await expect(check).toContainText('Identity waiting for a check')
  await expect(check.getByRole('link', { name: 'Check which film this is' })).toHaveCount(0)
})
