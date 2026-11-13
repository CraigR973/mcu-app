import { randomUUID } from 'node:crypto'
import type { Page } from '@playwright/test'
import { posters, unfold } from '../support/cinema-view.ts'
import { test as base, expect } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const json = (value: unknown) => `${sql(JSON.stringify(value))}::jsonb`

type Fixture = { today: string; plus: (days: number) => string; label: string; listingId: string }

// AC4: Movie night's At the cinema view and a page per film, on the nine venues as they stood on
// 4–5 Nov: Vue and GFT listing two days, the ODEONs seven, Cineworld and the IMAX the fortnight,
// Everyman's latest check failed, and ODEON Kilmarnock's saved listing stale. Rows go only into
// the harness's disposable Postgres; every page reads them through the real API.
const test = base.extend<{ cinema: Fixture }>({
  cinema: async ({ db }, use) => {
    const label = `ac4-e2e:${randomUUID()}`
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value
    const today = `${part('year')}-${part('month')}-${part('day')}`
    const plus = (days: number) => new Date(Date.parse(`${today}T12:00:00Z`) + days * 86400000).toISOString().slice(0, 10)
    const enabled = db.scalar(`SELECT json_object_agg(slug, collection_enabled)::text FROM cinema_venues`)
    db.sql(`UPDATE cinema_venues SET collection_enabled=true;
      INSERT INTO cinema_coverage (id,venue_id,local_date,status,observed,complete,last_attempt_utc,last_success_utc,source_update_label,error)
      SELECT gen_random_uuid(), v.id, d::date,
        CASE WHEN v.slug='everyman-glasgow' THEN 'failed' ELSE 'partial' END,
        v.slug <> 'everyman-glasgow' AND d::date <= ${sql(today)}::date + CASE WHEN v.slug IN ('vue-st-enoch','gft') THEN 1 WHEN v.slug LIKE 'odeon-%' THEN 6 ELSE 13 END,
        false, now() AT TIME ZONE 'utc',
        CASE WHEN v.slug='everyman-glasgow' THEN NULL WHEN v.slug='odeon-kilmarnock' THEN (now() AT TIME ZONE 'utc') - interval '40 hours' ELSE now() AT TIME ZONE 'utc' END,
        ${sql(label)}, CASE WHEN v.slug='everyman-glasgow' THEN 'Fixture source refused the latest check' END
      FROM cinema_venues v, generate_series(${sql(today)}::date, ${sql(today)}::date + 13, interval '1 day') d`)
    const venue = (slug: string) => JSON.parse(db.scalar(`SELECT json_build_object('id',id,'source',source)::text FROM cinema_venues WHERE slug=${sql(slug)}`)) as { id: string; source: string }
    const films: Record<string, string> = {}
    // One cinema film row per source, as the refresh writes them; linked rows share a TMDB id.
    const film = (key: string, slug: string, title: string, status: string, evidence: Record<string, unknown>) => {
      const id = randomUUID()
      films[`${key}:${slug}`] = id
      db.sql(`INSERT INTO cinema_films (id,source,source_key,title,identity_status,evidence,original_year) VALUES (${sql(id)},${sql(venue(slug).source)},${sql(`${label}:${key}:${slug}`)},${sql(title)},${sql(status)},${json(evidence)},${evidence.year ? Number(evidence.year) : 'NULL'})`)
      return id
    }
    const showing = (filmId: string, slug: string, day: string, hour: number, run: Record<string, unknown>, formats: string[] = ['Format.Projection.Digital'], stale = false) => {
      const booking = slug === 'vue-st-enoch' ? 'https://www.myvue.com/book-tickets/fixture' : slug === 'gft' ? 'https://www.glasgowfilm.org/checkout/showing/fixture' : slug === 'cineworld-silverburn' ? 'https://web.cineworld.co.uk/order/showtimes/fixture' : slug === 'science-centre-imax' ? 'https://www.tickettailor.com/events/gscimax/fixture' : 'https://www.odeon.co.uk/ticketing/seat-picker/fixture'
      const category = run.run === 'rerun' ? 'olderFilm' : run.run === 'firstRun' ? 'newRelease' : 'unclassified'
      db.sql(`INSERT INTO cinema_screenings (id,venue_id,film_id,source_key,identity_strength,local_date,source_local_start,starts_utc,formats,booking_url,release_category,category_evidence,confirmation,last_seen_utc) VALUES (${sql(randomUUID())},${sql(venue(slug).id)},${sql(filmId)},${sql(`${label}:${randomUUID()}`)},'opaque',${sql(day)},${sql(`${day}T${hour}:00:00`)},${sql(`${day}T${hour}:00:00`)},${json(formats)},${sql(booking)},${sql(category)},${json(run)},'confirmed',${stale ? "(now() AT TIME ZONE 'utc') - interval '40 hours'" : "now() AT TIME ZONE 'utc'"})`)
    }
    const linked = (tmdbId: number, poster: string, year: number) => ({ tmdbId, posterPath: poster, year, identity: { outcome: 'linked', reason: '', corroboration: ['the director'], others: [] } })
    const rerun = { run: 'rerun', runReason: 'UK release 1977 · rerun' }
    const firstRun = { run: 'firstRun', runReason: 'UK release 30 Oct 2026 · first run' }
    for (const slug of ['gft', 'odeon-glasgow-quay']) {
      const id = film('rocky', slug, 'Rocky (50th Anniversary)', 'verified', linked(9_100_001, '/ac4-rocky.jpg', 1976))
      showing(id, slug, plus(1), slug === 'gft' ? 18 : 20, { ...rerun, runReason: 'UK release 1977 · the cinema calls it an anniversary showing · rerun' })
    }
    for (const [slug, day, hour, formats] of [['cineworld-silverburn', 1, 19, ['Format.Projection.Digital']], ['cineworld-silverburn', 3, 20, ['Format.Projection.3d']], ['odeon-braehead', 2, 17, []], ['vue-st-enoch', 1, 21, ['IMAX']]] as const) {
      const id = films[`horse:${slug}`] ?? film('horse', slug, 'Wild Horse Nine', 'verified', linked(9_100_002, '/ac4-horse.jpg', 2026))
      showing(id, slug, plus(day), hour, firstRun, [...formats])
    }
    const clay = film('clay', 'odeon-kilmarnock', 'Clayface', 'verified', linked(9_100_003, '/ac4-clay.jpg', 2026))
    showing(clay, 'odeon-kilmarnock', plus(2), 19, firstRun, ['Format.Projection.Digital'], true)
    for (const slug of ['science-centre-imax', 'cineworld-silverburn']) {
      const id = film('hamnet', slug, 'Hamnet', 'verified', linked(9_100_004, '/ac4-hamnet.jpg', 2026))
      showing(id, slug, plus(9), 18, { run: 'firstRun', runReason: 'UK release 9 Jan 2026 · preview' }, slug === 'science-centre-imax' ? ['IMAX'] : ['Format.Projection.Digital'])
    }
    const waiting = { identity: { outcome: 'unlinked', reason: 'not yet looked up on TMDB', corroboration: [], others: [] } }
    const listingId = film('primetime', 'cineworld-silverburn', 'Primetime', 'unverified', waiting)
    showing(listingId, 'cineworld-silverburn', plus(1), 16, {})
    showing(film('primetime', 'vue-st-enoch', 'Primetime', 'unverified', waiting), 'vue-st-enoch', plus(1), 15, {})
    const event = film('golden', 'odeon-glasgow-quay', 'National Theatre Live: Golden Boy', 'event', { identity: { outcome: 'event', reason: 'a live or staged event, not a film', corroboration: [], others: [] } })
    showing(event, 'odeon-glasgow-quay', plus(5), 19, {})
    try {
      await use({ today, plus, label, listingId })
    } finally {
      db.sql(`DELETE FROM cinema_films WHERE source_key LIKE ${sql(`${label}:%`)}; DELETE FROM cinema_coverage WHERE source_update_label=${sql(label)};
        UPDATE cinema_venues v SET collection_enabled=(${sql(enabled)}::json->>v.slug)::boolean`)
    }
  },
})

async function phone(signedIn: (person: 'Craig' | 'Mark') => Promise<{ context: import('@playwright/test').BrowserContext; page: Page }>, person: 'Craig' | 'Mark', theme: string) {
  const session = await signedIn(person)
  await session.page.setViewportSize({ width: 375, height: 812 })
  await session.context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
  await posters(session.page)
  return session
}

const noSidewaysScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
/** "Fri 6 Nov", as the app writes a day. */
const dayLabel = (day: string) => `${WEEKDAYS[new Date(`${day}T12:00:00Z`).getUTCDay()]} ${Number(day.slice(8))} ${MONTHS[Number(day.slice(5, 7)) - 1]}`

test('Movie night folds past screenings, keeps open and planned ones on top, and plans a cinema trip', async ({ signedIn, api }, testInfo) => {
  const craig = await api('Craig')
  const planned = await craig.post<{ id: string }>('/movie-night', { filters: {}, plannedStart: new Date(Date.now() + 2 * 86400000).toISOString() })
  const ended = await craig.post<{ id: string }>('/movie-night', { filters: {} })
  await craig.post(`/movie-night/${ended.id}/end`, {})
  for (const person of ['Craig', 'Mark'] as const) {
    for (const theme of ['light', 'dark']) {
      const { page } = await phone(signedIn, person, theme)
      await page.goto('/movie-night')
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      const views = page.getByRole('navigation', { name: 'Movie night views' })
      await expect(views.getByRole('link', { name: 'At home' })).toHaveAttribute('aria-current', 'page')
      if (person === 'Craig') {
        await expect(page.getByRole('list', { name: 'Open and planned screenings' }).locator(`a[href="/movie-night/${planned.id}"]`)).toBeVisible()
        const fold = page.locator('details').filter({ hasText: /^Past screenings \(\d+\)/ })
        await expect(fold).not.toHaveAttribute('open', '')
        await expect(fold.locator(`a[href="/movie-night/${ended.id}"]`)).toBeHidden()
        await fold.getByText(/^Past screenings/).click()
        await expect(fold.locator(`a[href="/movie-night/${ended.id}"]`)).toBeVisible()
        await fold.getByText(/^Past screenings/).click()
      }
      const plan = page.getByRole('region', { name: 'Plan a cinema trip' })
      await expect(plan).toBeVisible()
      expect(await noSidewaysScroll(page)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ac4-movie-night-${person.toLowerCase()}-${theme}-375.png`) })
      await plan.getByRole('link', { name: 'See what’s on' }).click()
      await expect(page).toHaveURL(/\/movie-night\/cinema$/)
      await expect(views.getByRole('link', { name: 'At the cinema' })).toHaveAttribute('aria-current', 'page')
    }
  }
})

test('At the cinema reads film first at 375px, both themes and both people, with partial and stale coverage', async ({ signedIn, cinema }, testInfo) => {
  for (const person of ['Craig', 'Mark'] as const) {
    for (const theme of ['light', 'dark']) {
      const { page } = await phone(signedIn, person, theme)
      // AF3 (#372): every day at once is the default; AE5's "all" still reads as it.
      await page.goto('/movie-night/cinema?day=all')
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      const week = page.getByRole('region', { name: 'This week' })
      await expect(week.getByRole('article')).toHaveCount(3)
      // Widest first: Wild Horse Nine at three cinemas, then Rocky at two, then Clayface at one.
      await expect(week.getByRole('article').first()).toHaveAccessibleName('Wild Horse Nine')
      const horse = week.getByRole('article', { name: 'Wild Horse Nine' })
      await expect(horse).toContainText('First run')
      await expect(horse).toContainText('3 cinemas')
      const rocky = week.getByRole('article', { name: 'Rocky' })
      await expect(rocky).toContainText('Rerun')
      await expect(rocky).toContainText('2 cinemas')
      await expect(page.getByRole('region', { name: 'Coming up' }).getByRole('article', { name: 'Hamnet' })).toContainText('Preview')
      const listings = await unfold(page, 'Not matched to a film yet')
      await expect(listings.getByRole('article', { name: 'Primetime' })).toHaveCount(2)
      await expect((await unfold(page, 'Events and double bills')).getByRole('article', { name: 'National Theatre Live: Golden Boy' })).toBeVisible()
      const horizons = page.getByRole('region', { name: 'How far ahead cinemas list' })
      await expect(horizons).toContainText(`GFT, Vue St Enoch: listed only to ${dayLabel(cinema.plus(1))}`)
      await expect(horizons).toContainText(`ODEON Braehead, ODEON East Kilbride, ODEON Quay, ODEON Kilmarnock: listed only to ${dayLabel(cinema.plus(6))}`)
      await expect(horizons).toContainText('Everyman: no current listing · latest check failed')
      await expect(page.getByText('Partial coverage:', { exact: false })).toBeVisible()
      await expect(page.getByText('Some saved programmes are stale', { exact: false })).toBeVisible()
      expect(await noSidewaysScroll(page)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ac4-cinema-${person.toLowerCase()}-${theme}-375.png`) })
      await listings.scrollIntoViewIfNeeded()
      await page.screenshot({ path: testInfo.outputPath(`ac4-cinema-listings-${person.toLowerCase()}-${theme}-375.png`) })

      // The film page: every showing by day, then cinema, as time chips with their format.
      await horse.getByRole('link').click()
      await expect(page.getByRole('heading', { name: 'Wild Horse Nine', level: 1 })).toBeVisible()
      await expect(page).toHaveURL(/\/movie-night\/cinema\/tmdb-9100002$/)
      // AF3 (#372): a film's page opens on its first day; every showing is All days.
      await page.getByRole('group', { name: 'Day' }).getByRole('button', { name: 'All days', exact: true }).click()
      await expect(page).toHaveURL(/\/movie-night\/cinema\/tmdb-9100002\?day=all$/)
      const tomorrow = page.getByRole('region', { name: /^Tomorrow · / })
      await expect(tomorrow.getByRole('listitem', { name: /Cineworld|Vue/ })).toHaveCount(2)
      await expect(tomorrow.getByRole('link', { name: '21:00 IMAX, check tickets at Vue Glasgow St Enoch' })).toBeVisible()
      await expect(page.getByRole('link', { name: /20:00 3D, check tickets at Cineworld Glasgow Silverburn/ })).toBeVisible()
      await expect(page.getByRole('link', { name: /check tickets/ })).toHaveCount(4)
      await expect(page.getByText('UK release 30 Oct 2026 · first run', { exact: true })).toBeVisible()
      expect(await noSidewaysScroll(page)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ac4-film-${person.toLowerCase()}-${theme}-375.png`) })

      // A stale cinema's times show, but send nobody to book.
      await page.goBack()
      await page.getByRole('region', { name: 'This week' }).getByRole('article', { name: 'Clayface' }).getByRole('link').click()
      await expect(page.getByRole('heading', { name: 'Clayface', level: 1 })).toBeVisible()
      await expect(page.getByRole('listitem', { name: 'ODEON Kilmarnock' })).toContainText('Saved listing is stale · ticket links paused')
      await expect(page.getByRole('link', { name: /check tickets/ })).toHaveCount(0)
      await expect(page.getByText('Saved showing is stale', { exact: true })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(`ac4-film-stale-${person.toLowerCase()}-${theme}-375.png`) })
    }
  }
})

test('the run, day and cinema filters answer at once and come back from a film page', async ({ signedIn, cinema }) => {
  const { page } = await phone(signedIn, 'Mark', 'light')
  await page.goto('/movie-night/cinema?day=all')
  await page.getByRole('group', { name: 'Run' }).getByRole('button', { name: /^Older films/ }).click()
  await expect(page.getByRole('article')).toHaveCount(1)
  await expect(page).toHaveURL(/\?day=all&run=olderFilm$/)
  await page.getByRole('article', { name: 'Rocky' }).getByRole('link').click()
  await expect(page.getByRole('heading', { name: 'Rocky', level: 1 })).toBeVisible()
  // The anniversary is the cinemas' label, so the reason is the same at both and said once.
  await expect(page.getByText('UK release 1977 · the cinema calls it an anniversary showing · rerun', { exact: true })).toHaveCount(1)
  await expect(page.getByText('Listed as “Rocky (50th Anniversary)”', { exact: true })).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(/\?day=all&run=olderFilm$/)
  await expect(page.getByRole('article')).toHaveCount(1)
  await page.getByRole('group', { name: 'Run' }).getByRole('button', { name: /^All films/ }).click()
  await page.getByRole('group', { name: 'Day' }).getByRole('button', { name: dayLabel(cinema.plus(9)), exact: true }).click()
  await expect(page.getByRole('article')).toHaveCount(1)
  await expect(page.getByRole('article', { name: 'Hamnet' })).toBeVisible()
  await page.getByRole('group', { name: 'Day' }).getByRole('button', { name: 'All days' }).click()
  // AE4 (#355): the chip counts the cinemas, the Omniplex included, rather than saying nine.
  await page.getByText(/^Cinemas · all \d+/).click()
  for (const name of ['Cineworld Glasgow Silverburn', 'Vue Glasgow St Enoch', 'ODEON Braehead', 'Glasgow Science Centre IMAX']) {
    await page.getByRole('checkbox', { name }).uncheck()
  }
  await expect(page.getByRole('article', { name: 'Wild Horse Nine' })).toHaveCount(0)
  await expect(page.getByRole('article', { name: 'Rocky' })).toBeVisible()
})

test('a listing’s page keeps its address, and opens as the film once a morning links it', async ({ signedIn, db, cinema }) => {
  const { page } = await phone(signedIn, 'Craig', 'dark')
  await page.goto('/movie-night/cinema?day=all')
  await (await unfold(page, 'Not matched to a film yet')).getByRole('article', { name: 'Primetime' }).filter({ hasText: 'Cineworld' }).getByRole('link').click()
  const address = `/movie-night/cinema/listing-${cinema.listingId}`
  await expect(page).toHaveURL(new RegExp(`${address}$`))
  await expect(page.getByRole('region', { name: 'Which film this is' })).toContainText('Identity unverified')
  await expect(page.getByRole('region', { name: 'Also listed under this title' })).toContainText('Vue St Enoch')
  // A morning's matching links the listing (as AC3's store would) and labels its showing.
  db.sql(`UPDATE cinema_films SET identity_status='verified', evidence=${json({ tmdbId: 9_100_005, posterPath: '/ac4-prime.jpg', identity: { outcome: 'linked', reason: '', corroboration: ['the director'], others: [] } })} WHERE id=${sql(cinema.listingId)};
    UPDATE cinema_screenings SET release_category='newRelease', category_evidence=${json({ run: 'firstRun', runReason: 'UK release 30 Oct 2026 · first run' })} WHERE film_id=${sql(cinema.listingId)}`)
  await page.goto(address)
  await expect(page).toHaveURL(/\/movie-night\/cinema\/tmdb-9100005$/)
  await expect(page.getByRole('heading', { name: 'Primetime', level: 1 })).toBeVisible()
  await expect(page.getByText('First run', { exact: true })).toBeVisible()
  // The Vue listing of the title is still its own until it is matched too.
  await expect(page.getByRole('region', { name: 'Also listed under this title' })).toContainText('Not matched yet · Vue St Enoch')
})

test('Home shows this week’s cinema films as a poster strip, for both people in both themes', async ({ signedIn, cinema }, testInfo) => {
  void cinema // its rows are the strip's films
  for (const person of ['Craig', 'Mark'] as const) {
    for (const theme of ['light', 'dark']) {
      const { page } = await phone(signedIn, person, theme)
      await page.goto('/dashboard')
      const strip = page.getByRole('region', { name: 'At the cinema' })
      await expect(strip.getByRole('link', { name: 'At the cinema', exact: true })).toHaveAttribute('href', '/movie-night/cinema')
      // AB7's guard holds every way in until Home's first layout has arrived.
      await expect(page.getByRole('list', { name: 'The collection in numbers' })).toBeVisible()
      await expect(strip.getByRole('link', { name: 'At the cinema', exact: true })).not.toHaveAttribute('aria-disabled', 'true')
      const cards = strip.getByRole('list', { name: 'This week at the cinema' }).getByRole('listitem')
      // AF3 (#372): the week's older film leads, then the rest widest first, then See all.
      await expect(cards).toHaveCount(4)
      await expect(cards.first()).toContainText('Rocky')
      await expect(cards.first()).toContainText('Rerun2 cinemas')
      await expect(cards.nth(1)).toContainText('Wild Horse Nine')
      await expect(cards.nth(1)).toContainText('First run3 cinemas')
      await expect(cards.last().getByRole('link', { name: 'See all films at the cinema' })).toHaveAttribute('href', '/movie-night/cinema')
      await strip.scrollIntoViewIfNeeded()
      expect(await noSidewaysScroll(page)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ac4-home-${person.toLowerCase()}-${theme}-375.png`) })
      await cards.nth(1).getByRole('link').click()
      await expect(page).toHaveURL(/\/movie-night\/cinema\/tmdb-91000\d\d$/)
    }
  }
})

// AF4 (#372, snag 4): Back from a film at the cinema, and a filter, keep At the cinema's place.
// Here for this file's cinema rows; the rest of AF4's cases are in af4.spec.ts.
async function scrolledTo(box: import('@playwright/test').Locator, top: number): Promise<number> {
  await box.evaluate((element, to) => { element.scrollTop = to }, top)
  await expect.poll(() => box.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
  return box.evaluate(element => element.scrollTop)
}

test('AF4 Back from a film at the cinema puts At the cinema where it was', async ({ signedIn, cinema }, testInfo) => {
  void cinema // its rows make the view tall enough to scroll
  const { page } = await signedIn('Mark')
  // A short screen, so Coming up is well below the first view.
  await page.setViewportSize({ width: 375, height: 600 })
  await page.goto('/movie-night/cinema')
  const main = page.locator('#main-content')
  const later = page.getByRole('region', { name: 'Coming up' }).getByRole('article').first().getByRole('link').first()
  await later.scrollIntoViewIfNeeded()
  // Where the reader is as they tap: the click itself scrolls nothing now.
  const before = await main.evaluate(element => element.scrollTop)
  expect(before).toBeGreaterThan(100)
  await later.click()
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  expect(await main.evaluate(element => element.scrollTop)).toBe(0)

  // The browser's own Back.
  await page.goBack()
  await expect(page).toHaveURL(/\/movie-night\/cinema$/)
  await expect.poll(() => main.evaluate(element => element.scrollTop)).toBeGreaterThanOrEqual(before - 2)
  expect(await main.evaluate(element => element.scrollTop)).toBeLessThanOrEqual(before + 2)
  await page.screenshot({ path: testInfo.outputPath('af4-cinema-back-375.png') })
})

test('AF4 a filter that replaces the address keeps the place', async ({ signedIn, cinema }) => {
  void cinema // its rows make the view tall enough to scroll
  const { page } = await signedIn('Craig')
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/movie-night/cinema')
  const main = page.locator('#main-content')
  await expect(page.getByRole('region', { name: 'This week' }).getByRole('article').first()).toBeVisible()
  const before = await scrolledTo(main, 300)
  // The run chips replace the address. Pressed where they are, without scrolling to them first.
  await page.getByRole('group', { name: 'Run' }).getByRole('button', { name: /^Older films/ }).evaluate(element => { (element as HTMLElement).click() })
  await expect(page).toHaveURL(/run=olderFilm/)
  // Not sent back to the top: the place stays, as far as the shorter list allows.
  expect(before).toBeGreaterThan(0)
  await expect.poll(() => main.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
})
