import { randomUUID } from 'node:crypto'
import { posters } from '../support/cinema-view.ts'
import { test as base, expect, type Session } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const json = (value: unknown) => `${sql(JSON.stringify(value))}::jsonb`

const TITLE = 'Paper Kites'
const TMDB = 9_400_001
const IMDB = 'tt9400001'
const LISTING = 'Mystery Matinee'

type Fixture = { listingKey: string }

// AE6 (#355, points 5 and 6): a matched cinema film links to Letterboxd by its TMDB id and to
// IMDb, and Propose a trip says beside each person whether they have seen it. Mark watched it
// twice, the latest on 12 Mar 2024; Craig never has. A listing not matched yet gets a Letterboxd
// search only, and the sheet says nothing of who has seen it. Tomorrow's showings, so the case
// reads the same at any hour. Rows go only into the harness's disposable Postgres, and every page
// reads them through the real API.
const test = base.extend<{ ae6: Fixture }>({
  ae6: async ({ db }, use) => {
    const label = `ae6-e2e:${randomUUID()}`
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value
    const today = `${part('year')}-${part('month')}-${part('day')}`
    const day = new Date(Date.parse(`${today}T12:00:00Z`) + 86400000).toISOString().slice(0, 10)
    const venues = JSON.parse(db.scalar(`SELECT json_object_agg(slug, json_build_object('id',id,'source',source,'enabled',collection_enabled))::text FROM cinema_venues WHERE slug IN ('cineworld-silverburn','vue-st-enoch')`)) as Record<string, { id: string; source: string; enabled: boolean }>
    const movie = randomUUID()
    const watches = [randomUUID(), randomUUID()]
    const films = { film: randomUUID(), listing: randomUUID() }
    try {
      db.sql(`UPDATE cinema_venues SET collection_enabled=true WHERE slug IN ('cineworld-silverburn','vue-st-enoch');
        INSERT INTO cinema_coverage (id,venue_id,local_date,status,observed,complete,last_attempt_utc,last_success_utc,source_update_label)
        SELECT gen_random_uuid(), id, ${sql(day)}, 'partial', true, false, now() AT TIME ZONE 'utc', now() AT TIME ZONE 'utc', ${sql(label)}
        FROM cinema_venues WHERE slug IN ('cineworld-silverburn','vue-st-enoch') ON CONFLICT (venue_id, local_date) DO NOTHING;
        INSERT INTO cinema_films (id,source,source_key,title,identity_status,evidence,original_year) VALUES
          (${sql(films.film)},${sql(venues['cineworld-silverburn'].source)},${sql(`${label}:film`)},${sql(TITLE)},'verified',
           ${json({ tmdbId: TMDB, imdbId: IMDB, posterPath: '/ae6-kites.jpg', identity: { outcome: 'linked', reason: '', corroboration: ['the director'], others: [] } })},2026),
          (${sql(films.listing)},${sql(venues['vue-st-enoch'].source)},${sql(`${label}:listing`)},${sql(LISTING)},'unverified',
           ${json({ identity: { outcome: 'unlinked', reason: 'not yet looked up on TMDB', corroboration: [], others: [] } })},NULL);
        INSERT INTO cinema_screenings (id,venue_id,film_id,source_key,identity_strength,local_date,source_local_start,starts_utc,formats,booking_url,release_category,category_evidence,confirmation,last_seen_utc) VALUES
          (gen_random_uuid(),${sql(venues['cineworld-silverburn'].id)},${sql(films.film)},${sql(`${label}:1`)},'opaque',${sql(day)},${sql(`${day}T19:30:00`)},${sql(`${day}T19:30:00`)},'["Format.Projection.Digital"]'::jsonb,'https://web.cineworld.co.uk/order/showtimes/ae6','newRelease',${json({ run: 'firstRun', runReason: 'UK release 6 Nov 2026 · first run' })},'confirmed',now() AT TIME ZONE 'utc'),
          (gen_random_uuid(),${sql(venues['vue-st-enoch'].id)},${sql(films.listing)},${sql(`${label}:2`)},'opaque',${sql(day)},${sql(`${day}T14:00:00`)},${sql(`${day}T14:00:00`)},'[]'::jsonb,'https://www.myvue.com/book-tickets/summary/ae6','unclassified','{}'::jsonb,'confirmed',now() AT TIME ZONE 'utc');
        INSERT INTO movies (id,title,year,tmdb_id,media_type) VALUES (${sql(movie)},${sql(TITLE)},2026,${TMDB},'film');
        INSERT INTO watch_log (id,movie_id,user_id,watched_at,is_rewatch)
          SELECT ${sql(watches[0])},${sql(movie)},id,'2022-01-05',false FROM profiles WHERE display_name='Mark';
        INSERT INTO watch_log (id,movie_id,user_id,watched_at,is_rewatch)
          SELECT ${sql(watches[1])},${sql(movie)},id,'2024-03-12',true FROM profiles WHERE display_name='Mark'`)
      await use({ listingKey: `listing-${films.listing}` })
    } finally {
      db.sql(`DELETE FROM watch_log WHERE id IN (${watches.map(sql).join(',')}); DELETE FROM movies WHERE id=${sql(movie)};
        DELETE FROM cinema_films WHERE source_key LIKE ${sql(`${label}:%`)}; DELETE FROM cinema_coverage WHERE source_update_label=${sql(label)};
        ${Object.values(venues).map(venue => `UPDATE cinema_venues SET collection_enabled=${String(venue.enabled)} WHERE id=${sql(venue.id)};`).join(' ')}`)
    }
  },
})

async function phone(signedIn: (person: 'Craig' | 'Mark') => Promise<Session>, person: 'Craig' | 'Mark', theme: 'light' | 'dark'): Promise<Session> {
  const session = await signedIn(person)
  await session.page.setViewportSize({ width: 375, height: 812 })
  await session.context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
  await posters(session.page)
  return session
}

const noSidewaysScroll = (session: Session) => session.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

test('AE6 a matched film links to Letterboxd and IMDb, and Propose a trip says who has seen it, at 375 px in both themes for both people', async ({ signedIn, ae6 }, testInfo) => {
  void ae6 // its rows are the page's film
  for (const [person, other, seen] of [['Craig', 'Mark', 'Seen · 12 Mar 2024'], ['Mark', 'Craig', 'Not seen']] as const) {
    for (const theme of ['light', 'dark'] as const) {
      const session = await phone(signedIn, person, theme)
      const { page } = session
      await page.goto(`/movie-night/cinema/tmdb-${String(TMDB)}`)
      await expect(page.getByRole('heading', { name: TITLE, level: 1 })).toBeVisible()
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      const letterboxd = page.getByRole('link', { name: 'Letterboxd', exact: true })
      await expect(letterboxd).toHaveAttribute('href', `https://letterboxd.com/tmdb/${String(TMDB)}/`)
      const imdb = page.getByRole('link', { name: 'IMDb', exact: true })
      await expect(imdb).toHaveAttribute('href', `https://www.imdb.com/title/${IMDB}/`)
      for (const link of [letterboxd, imdb]) {
        await expect(link).toHaveAttribute('target', '_blank')
        await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
      }
      expect(await noSidewaysScroll(session)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ae6-film-${person.toLowerCase()}-${theme}-375.png`) })

      await page.getByRole('button', { name: 'Propose a trip' }).click()
      const sheet = page.getByRole('dialog', { name: 'Propose a trip' })
      // Their latest watch of it, beside the box; the box keeps the person's name alone.
      await expect(sheet.getByRole('checkbox', { name: other, exact: true })).toHaveAccessibleDescription(seen)
      await expect(sheet.getByText(seen, { exact: true }).first()).toBeVisible()
      expect(await noSidewaysScroll(session)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ae6-invite-${person.toLowerCase()}-${theme}-375.png`) })
      await session.context.close()
    }
  }
})

test('AE6 a listing not matched yet gets a Letterboxd search only, and the sheet says nothing of who has seen it', async ({ signedIn, ae6 }, testInfo) => {
  for (const [person, other, theme] of [['Craig', 'Mark', 'light'], ['Mark', 'Craig', 'dark']] as const) {
    const session = await phone(signedIn, person, theme)
    const { page } = session
    await page.goto(`/movie-night/cinema/${ae6.listingKey}`)
    await expect(page.getByRole('heading', { name: LISTING, level: 1 })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Search Letterboxd', exact: true })).toHaveAttribute('href', 'https://letterboxd.com/search/Mystery%20Matinee/')
    await expect(page.getByRole('link', { name: 'IMDb', exact: true })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Letterboxd', exact: true })).toHaveCount(0)
    await page.screenshot({ path: testInfo.outputPath(`ae6-listing-${person.toLowerCase()}-${theme}-375.png`) })
    await page.getByRole('button', { name: 'Propose a trip' }).click()
    const sheet = page.getByRole('dialog', { name: 'Propose a trip' })
    const box = sheet.getByRole('checkbox', { name: other, exact: true })
    await expect(box).toBeVisible()
    await expect(box).not.toHaveAttribute('aria-describedby', /.+/)
    await expect(sheet.getByText(/^(Seen · |Not seen$)/)).toHaveCount(0)
    await session.context.close()
  }
})
