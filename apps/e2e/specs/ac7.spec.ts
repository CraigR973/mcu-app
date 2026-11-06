import { randomUUID } from 'node:crypto'
import type { BrowserContext, Page } from '@playwright/test'
import { test as base, expect } from '../support/test.ts'
import { world } from '../support/world.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const json = (value: unknown) => `${sql(JSON.stringify(value))}::jsonb`

/** TMDB ids the fake world lists for this case: two discs, three cinema releases. */
const FOUR_K = 9_200_011
const BLU_RAY = 9_200_012
const SHOWING = 9_200_001
const ELSEWHERE = 9_200_002
const UNMATCHED = 9_200_003
const TITLES = {
  fourK: 'AC7 Arcade Nights',
  bluRay: 'AC7 Harbour Lights',
  showing: 'AC7 The Lighthouse Keeper',
  elsewhere: 'AC7 Far From Glasgow',
  unmatched: 'AC7 Paper Moon Rising',
}

type Fixture = {
  /** The first sale after today, and the month the discs come out in with it. */
  sale: { day: string; title: string }
  discMonth: string
  /** The month the three cinema releases open in: tomorrow's. */
  cinemaMonth: string
}

// AC7: Releases as two calendars, filled the way production fills them. The fake TMDB lists two
// discs out on the day of the next sale and three cinema releases opening tomorrow, the admin
// endpoint "Refresh from TMDB" calls writes them, and the sale seasons come from their own admin
// endpoint. One cinema release is showing at Vue and GFT as a linked film; another shares its
// title with a Cineworld listing not matched to a film yet. Cinema rows go only into the
// harness's disposable Postgres, as AC4's do.
const test = base.extend<{ releases: Fixture }>({
  releases: async ({ db, api, cleanWorld }, use) => {
    void cleanWorld
    const label = `ac7-e2e:${randomUUID()}`
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value
    const today = `${part('year')}-${part('month')}-${part('day')}`
    const plus = (days: number) => new Date(Date.parse(`${today}T12:00:00Z`) + days * 86400000).toISOString().slice(0, 10)
    const craig = await api('Craig')

    const salesBefore = db.scalar(`SELECT COALESCE(string_agg(id::text, ','), '') FROM release_calendar WHERE release_type='sale_event'`)
    for (const year of [Number(today.slice(0, 4)), Number(today.slice(0, 4)) + 1]) await craig.post(`/notifications/seed-sale-seasons?year=${year}`)
    const [saleDay, saleTitle] = db.scalar(`SELECT release_date::text || '|' || title FROM release_calendar
      WHERE release_type='sale_event' AND release_date > ${sql(today)}::date AND release_date <= ${sql(plus(183))}::date
      ORDER BY release_date, title LIMIT 1`).split('|')

    const genreIds = [18, 80, 53, 35, 878, 27, 12, 9648, 10402, 37]
    world.setScenario({
      tmdb: {
        releases: [
          { id: FOUR_K, title: TITLES.fourK, genreIds, dates: [{ type: 5, date: saleDay, note: '4K Ultra HD Blu-ray' }] },
          { id: BLU_RAY, title: TITLES.bluRay, genreIds, dates: [{ type: 5, date: saleDay, note: 'Blu-ray' }] },
          { id: SHOWING, title: TITLES.showing, genreIds, dates: [{ type: 3, date: plus(1) }] },
          { id: ELSEWHERE, title: TITLES.elsewhere, genreIds, dates: [{ type: 3, date: plus(1) }] },
          { id: UNMATCHED, title: TITLES.unmatched, genreIds, dates: [{ type: 3, date: plus(1) }] },
        ],
      },
    })
    // A refresh a read started earlier would answer "already refreshing"; let it finish first.
    await expect.poll(() => db.scalar(`SELECT (last_started_utc IS NULL OR last_finished_utc >= last_started_utc)::text FROM calendar_refresh_state WHERE id=1`) || 'true').toBe('true')
    await craig.post('/calendar/ingest')

    const enabled = db.scalar(`SELECT json_object_agg(slug, collection_enabled)::text FROM cinema_venues`)
    db.sql(`UPDATE cinema_venues SET collection_enabled=true;
      INSERT INTO cinema_coverage (id,venue_id,local_date,status,observed,complete,last_attempt_utc,last_success_utc,source_update_label,error)
      SELECT gen_random_uuid(), v.id, d::date, 'partial', true, false, now() AT TIME ZONE 'utc', now() AT TIME ZONE 'utc', ${sql(label)}, NULL
      FROM cinema_venues v, generate_series(${sql(today)}::date, ${sql(today)}::date + 13, interval '1 day') d
      ON CONFLICT DO NOTHING`)
    const venue = (slug: string) => JSON.parse(db.scalar(`SELECT json_build_object('id',id,'source',source)::text FROM cinema_venues WHERE slug=${sql(slug)}`)) as { id: string; source: string }
    const film = (key: string, slug: string, title: string, status: string, evidence: Record<string, unknown>) => {
      const id = randomUUID()
      db.sql(`INSERT INTO cinema_films (id,source,source_key,title,identity_status,evidence,original_year) VALUES (${sql(id)},${sql(venue(slug).source)},${sql(`${label}:${key}:${slug}`)},${sql(title)},${sql(status)},${json(evidence)},${evidence.year ? Number(evidence.year) : 'NULL'})`)
      return id
    }
    const showing = (filmId: string, slug: string, day: string, hour: number, run: Record<string, unknown>) => {
      const category = run.run === 'firstRun' ? 'newRelease' : 'unclassified'
      db.sql(`INSERT INTO cinema_screenings (id,venue_id,film_id,source_key,identity_strength,local_date,source_local_start,starts_utc,formats,booking_url,release_category,category_evidence,confirmation,last_seen_utc) VALUES (${sql(randomUUID())},${sql(venue(slug).id)},${sql(filmId)},${sql(`${label}:${randomUUID()}`)},'opaque',${sql(day)},${sql(`${day}T${hour}:00:00`)},${sql(`${day}T${hour}:00:00`)},${json(['Format.Projection.Digital'])},NULL,${sql(category)},${json(run)},'confirmed',now() AT TIME ZONE 'utc')`)
    }
    const firstRun = { run: 'firstRun', runReason: `UK release ${plus(1)} · first run` }
    const linked = { tmdbId: SHOWING, posterPath: '/ac7-lighthouse.jpg', year: Number(today.slice(0, 4)), identity: { outcome: 'linked', reason: '', corroboration: ['the director'], others: [] } }
    showing(film('lighthouse', 'vue-st-enoch', TITLES.showing, 'verified', linked), 'vue-st-enoch', plus(1), 19, firstRun)
    showing(film('lighthouse', 'gft', TITLES.showing, 'verified', linked), 'gft', plus(2), 18, firstRun)
    const waiting = { identity: { outcome: 'unlinked', reason: 'not yet looked up on TMDB', corroboration: [], others: [] } }
    showing(film('paper-moon', 'cineworld-silverburn', TITLES.unmatched, 'unverified', waiting), 'cineworld-silverburn', plus(1), 16, {})

    try {
      await use({ sale: { day: saleDay, title: saleTitle }, discMonth: saleDay.slice(0, 7), cinemaMonth: plus(1).slice(0, 7) })
    } finally {
      const kept = salesBefore ? salesBefore.split(',').map(sql).join(',') : `'00000000-0000-0000-0000-000000000000'`
      db.sql(`DELETE FROM cinema_films WHERE source_key LIKE ${sql(`${label}:%`)}; DELETE FROM cinema_coverage WHERE source_update_label=${sql(label)};
        UPDATE cinema_venues v SET collection_enabled=(${sql(enabled)}::json->>v.slug)::boolean;
        DELETE FROM release_calendar WHERE tmdb_id IN (${[FOUR_K, BLU_RAY, SHOWING, ELSEWHERE, UNMATCHED].join(',')});
        DELETE FROM release_calendar WHERE release_type='sale_event' AND id::text NOT IN (${kept})`)
    }
  },
})

/** Posters from the fake world are not images; draw each as a tinted card, as AC4's case does. */
async function posters(page: Page) {
  await page.route('https://image.tmdb.org/t/p/**', async route => {
    const name = new URL(route.request().url()).pathname.split('/').pop() ?? ''
    const hue = [...name].reduce((sum, c) => sum + c.charCodeAt(0), 0) % 360
    await route.fulfill({
      contentType: 'image/svg+xml',
      body: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 300"><rect width="200" height="300" fill="hsl(${hue} 45% 32%)"/></svg>`,
    })
  })
}

async function phone(signedIn: (person: 'Craig' | 'Mark') => Promise<{ context: BrowserContext; page: Page }>, person: 'Craig' | 'Mark', theme: string) {
  const session = await signedIn(person)
  await session.page.setViewportSize({ width: 375, height: 812 })
  await session.context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
  await posters(session.page)
  return session
}

const noSidewaysScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

test('Releases is two calendars at 375px, both themes and both people, each with its own month', async ({ signedIn, releases }, testInfo) => {
  for (const person of ['Craig', 'Mark'] as const) {
    for (const theme of ['light', 'dark']) {
      const { page } = await phone(signedIn, person, theme)
      await page.goto(`/calendar?month=${releases.discMonth}`)
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      const views = page.getByRole('navigation', { name: 'Release calendars' })
      await expect(views.getByRole('link', { name: 'Disc releases' })).toHaveAttribute('aria-current', 'page')

      // Disc releases: the month's 4K, Blu-ray and sale dates, and no cinema date.
      const discs = page.getByRole('region', { name: 'Disc releases by month' })
      await expect(discs.getByText(TITLES.fourK)).toBeVisible()
      await expect(discs.getByText(TITLES.bluRay)).toBeVisible()
      await expect(discs.getByText(releases.sale.title).first()).toBeVisible()
      await expect(discs.getByText(TITLES.showing)).toHaveCount(0)
      const show = discs.getByRole('group', { name: 'Show' })
      await show.getByRole('button', { name: /^Sale events/ }).click()
      await expect(page).toHaveURL(/show=sales/)
      await expect(discs.getByText(TITLES.fourK)).toHaveCount(0)
      await expect(discs.getByText(releases.sale.title).first()).toBeVisible()
      await show.getByRole('button', { name: /^All/ }).click()
      await expect(discs.getByText(TITLES.fourK)).toBeVisible()
      // Refresh from TMDB is the admin's, on both calendars, as it was.
      await expect(page.getByRole('button', { name: 'Refresh from TMDB' })).toHaveCount(person === 'Craig' ? 1 : 0)
      expect(await noSidewaysScroll(page)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ac7-disc-${person.toLowerCase()}-${theme}-375.png`) })

      // Cinema releases: the month goes with the switch; then the month the cinema dates are in.
      await views.getByRole('link', { name: 'Cinema releases' }).click()
      await expect(page).toHaveURL(new RegExp(`/calendar/cinema\\?month=${releases.discMonth}$`))
      await expect(views.getByRole('link', { name: 'Cinema releases' })).toHaveAttribute('aria-current', 'page')
      await page.goto(`/calendar/cinema?month=${releases.cinemaMonth}`)
      const cinema = page.getByRole('region', { name: 'Cinema releases by month' })
      const link = cinema.getByRole('link', { name: new RegExp(TITLES.showing) })
      await expect(link).toHaveAttribute('href', `/movie-night/cinema/tmdb-${SHOWING}`)
      await expect(link).toContainText('At 2 of your cinemas')
      // Not showing at the nine, and a title shared with a listing not matched yet: no link.
      await expect(cinema.getByText(TITLES.elsewhere)).toBeVisible()
      await expect(cinema.getByRole('link', { name: new RegExp(TITLES.elsewhere) })).toHaveCount(0)
      await expect(cinema.getByText(TITLES.unmatched)).toBeVisible()
      await expect(cinema.getByRole('link', { name: new RegExp(TITLES.unmatched) })).toHaveCount(0)
      await expect(cinema.getByText(/cinema listings? (is|are) not matched to a film yet/)).toBeVisible()
      await expect(cinema.getByText(TITLES.fourK)).toHaveCount(0)
      await expect(page.getByRole('button', { name: 'Refresh from TMDB' })).toHaveCount(person === 'Craig' ? 1 : 0)
      expect(await noSidewaysScroll(page)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ac7-cinema-${person.toLowerCase()}-${theme}-375.png`) })
    }
  }
})

test('A cinema release showing at one of the nine opens its film page, and back returns to the month', async ({ signedIn, releases }, testInfo) => {
  const { page } = await phone(signedIn, 'Mark', 'dark')
  await page.goto(`/calendar/cinema?month=${releases.cinemaMonth}`)
  await page.getByRole('region', { name: 'Cinema releases by month' }).getByRole('link', { name: new RegExp(TITLES.showing) }).click()
  await expect(page).toHaveURL(new RegExp(`/movie-night/cinema/tmdb-${SHOWING}$`))
  await expect(page.getByRole('heading', { level: 1, name: TITLES.showing })).toBeVisible()
  await expect(page.getByText('Vue Glasgow St Enoch').first()).toBeVisible()
  await expect(page.getByText('Glasgow Film Theatre').first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('ac7-film-page-mark-dark-375.png') })
  await page.goBack()
  await expect(page).toHaveURL(new RegExp(`/calendar/cinema\\?month=${releases.cinemaMonth}$`))
  await expect(page.getByRole('link', { name: new RegExp(TITLES.showing) }).first()).toBeVisible()
  // Coming soon sits on the cinema calendar now, and opens the same page.
  const soon = page.getByRole('region', { name: 'Coming soon' })
  await expect(soon.getByRole('link', { name: new RegExp(TITLES.showing) })).toHaveAttribute('href', `/movie-night/cinema/tmdb-${SHOWING}`)
})

test("Home's Coming to disc stays disc-only, and Refresh from TMDB still reports as it did", async ({ signedIn, releases }) => {
  const { page } = await phone(signedIn, 'Craig', 'light')
  await page.goto('/dashboard')
  const coming = page.getByRole('region', { name: /Coming to disc/ })
  await expect(coming.getByText(TITLES.fourK)).toBeVisible()
  await expect(coming.getByText(TITLES.showing)).toHaveCount(0)
  await expect(coming.getByText(TITLES.elsewhere)).toHaveCount(0)
  await coming.getByRole('link', { name: 'All releases' }).click()
  await expect(page).toHaveURL(/\/calendar$/)
  // The fixture ran the same refresh, so pressing it again finds every release already there.
  await page.getByRole('button', { name: 'Refresh from TMDB' }).click()
  await expect(page.getByRole('status').filter({ hasText: /^0 new, 0 moved, \d+\s+unchanged\.$/ })).toBeVisible()
  await page.goto(`/calendar?month=${releases.discMonth}`)
  await expect(page.getByRole('region', { name: 'Disc releases by month' }).getByText(TITLES.bluRay)).toBeVisible()
})

test('One press gives a feed per calendar and one for both; the next press stops all three', async ({ signedIn, api, releases }) => {
  void releases
  const before = await (await api('Craig')).post<{ path: string }>('/calendar/subscribe')
  const { page } = await phone(signedIn, 'Craig', 'dark')
  await page.goto('/calendar/cinema')
  await page.getByRole('button', { name: 'Get my calendar links' }).click()
  const link = async (name: string) => (await page.getByRole('group', { name: new RegExp(`^${name}`) }).locator('code').textContent())?.trim() ?? ''
  const cinemaUrl = await link('Cinema releases')
  const discUrl = await link('Disc releases')
  const bothUrl = await link('Both calendars')
  expect(cinemaUrl).toMatch(/\/api\/v1\/calendar\.ics\?token=[\w-]+&calendar=cinema$/)
  expect(discUrl).toBe(cinemaUrl.replace(/cinema$/, 'disc'))
  expect(bothUrl).toBe(cinemaUrl.replace(/&calendar=cinema$/, ''))
  await expect(page.getByText(/Your previous links have stopped working/)).toBeVisible()

  const feed = async (url: string) => {
    const response = await fetch(url)
    return { status: response.status, text: await response.text() }
  }
  const disc = await feed(discUrl)
  expect(disc.status).toBe(200)
  expect(disc.text).toContain('X-WR-CALNAME:MCU — Disc releases')
  expect(disc.text).toContain(`4K UHD: ${TITLES.fourK}`)
  expect(disc.text).toContain(`Blu-ray: ${TITLES.bluRay}`)
  expect(disc.text).toContain('SUMMARY:Sale: ')
  expect(disc.text).not.toContain(TITLES.showing)
  const cinema = await feed(cinemaUrl)
  expect(cinema.text).toContain('X-WR-CALNAME:MCU — Cinema releases')
  expect(cinema.text).toContain(`In cinemas: ${TITLES.showing}`)
  expect(cinema.text).not.toContain(TITLES.fourK)
  // The feed installed calendars follow: every type, under its old name.
  const both = await feed(bothUrl)
  expect(both.text).toContain('X-WR-CALNAME:MCU — Release calendar')
  expect(both.text).toContain(`4K UHD: ${TITLES.fourK}`)
  expect(both.text).toContain(`In cinemas: ${TITLES.showing}`)
  // The link from before this press stopped, as a token that never existed would.
  const old = await feed(`${new URL(bothUrl).origin}${before.path}`)
  expect(old.status).toBe(404)
})
