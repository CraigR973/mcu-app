import { randomUUID } from 'node:crypto'
import { filmLink, posters, unfold } from '../support/cinema-view.ts'
import { test as base, expect, type Session } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const json = (value: unknown) => `${sql(JSON.stringify(value))}::jsonb`
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
/** "Wed 11 Nov", as the app writes a day. */
const dayLabel = (day: string) => `${WEEKDAYS[new Date(`${day}T12:00:00Z`).getUTCDay()]} ${Number(day.slice(8))} ${MONTHS[Number(day.slice(5, 7)) - 1]}`
const minutes = (clock: string) => Number(clock.slice(0, 2)) * 60 + Number(clock.slice(3, 5))
/** The instant of a London wall-clock time, so the case reads the same in summer time. */
function london(day: string, clock: string): Date {
  const guess = Date.parse(`${day}T${clock}:00Z`)
  const shown = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(guess)
  const ahead = ((minutes(shown) - minutes(clock) + 2160) % 1440) - 720
  return new Date(guess - ahead * 60_000)
}
const naive = (instant: Date) => instant.toISOString().slice(0, 19)

const LANTERN = 'The Lantern Keeper'
const HARBOUR = 'Harbour Lights'
const NORTHERN = 'Northern Line'
const BOOKING: Record<string, string> = {
  'vue-st-enoch': 'https://www.myvue.com/book-tickets/summary/ae5',
  gft: 'https://www.glasgowfilm.org/checkout/showing/ae5',
  'cineworld-silverburn': 'https://web.cineworld.co.uk/order/showtimes/ae5',
  'science-centre-imax': 'https://www.tickettailor.com/events/gscimax/ae5',
  'everyman-glasgow': 'https://purchase.everymancinema.com/launch/ticketing/ae5',
  'omniplex-glasgow-renfrew-street': 'https://www.omniplexcinemas.co.uk/booking/seats/glasgow-renfrew-street/ae5',
}
/** Each time's own ticket link, so a chip is known by where it goes. */
const booking = (slug: string, clock: string) => `${BOOKING[slug] ?? 'https://www.odeon.co.uk/ticketing/seat-picker/ae5'}-${clock.replace(':', '')}`

type Week = { plus: (days: number) => string; morning: Date; evening: Date }

// AE5 (#355, points 4, 8 and 13): At the cinema day by day, at all ten cinemas. The phone's clock
// is tomorrow at 10:00 in London, after that morning's check, so the case reads the same whatever
// hour it runs: tomorrow is the phone's today, and a 09:30 time has already started. GFT and Vue
// list only two days ahead; the day after that has nothing anywhere. Rows go only into the
// harness's disposable Postgres, and every page reads them through the real API.
const test = base.extend<{ week: Week }>({
  week: async ({ db }, use) => {
    const label = `ae5-e2e:${randomUUID()}`
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value
    const today = `${part('year')}-${part('month')}-${part('day')}`
    const plus = (days: number) => new Date(Date.parse(`${today}T12:00:00Z`) + days * 86400000).toISOString().slice(0, 10)
    const checked = naive(london(plus(1), '08:00'))
    const enabled = db.scalar(`SELECT json_object_agg(slug, collection_enabled)::text FROM cinema_venues`)
    expect(Object.keys(JSON.parse(enabled) as Record<string, boolean>)).toHaveLength(10)
    // The fortnight's coverage is this case's own. Rows an earlier case left (AC6's morning run
    // writes some) are set aside first and put back afterwards, exactly as they were.
    const fortnight = `local_date BETWEEN ${sql(today)}::date AND ${sql(today)}::date + 13`
    const kept = db.scalar(`SELECT coalesce(json_agg(c), '[]'::json)::text FROM cinema_coverage c WHERE ${fortnight}`)
    try {
      db.sql(`DELETE FROM cinema_coverage WHERE ${fortnight};
        UPDATE cinema_venues SET collection_enabled=true;
        INSERT INTO cinema_coverage (id,venue_id,local_date,status,observed,complete,last_attempt_utc,last_success_utc,source_update_label)
        SELECT gen_random_uuid(), v.id, d::date, 'partial',
          d::date <= ${sql(today)}::date + CASE WHEN v.slug IN ('vue-st-enoch','gft') THEN 2 ELSE 13 END,
          false, ${sql(checked)}, ${sql(checked)}, ${sql(label)}
        FROM cinema_venues v, generate_series(${sql(today)}::date, ${sql(today)}::date + 13, interval '1 day') d`)
      const venue = (slug: string) => JSON.parse(db.scalar(`SELECT json_build_object('id',id,'source',source)::text FROM cinema_venues WHERE slug=${sql(slug)}`)) as { id: string; source: string }
      const films: Record<string, string> = {}
      // One cinema film row per source and cinema, as the refresh writes them; linked rows share a TMDB id.
      const film = (key: string, slug: string, title: string, status: string, evidence: Record<string, unknown>) => {
        const known = films[`${key}:${slug}`]
        if (known) return known
        const id = randomUUID()
        films[`${key}:${slug}`] = id
        db.sql(`INSERT INTO cinema_films (id,source,source_key,title,identity_status,evidence,original_year) VALUES (${sql(id)},${sql(venue(slug).source)},${sql(`${label}:${key}:${slug}`)},${sql(title)},${sql(status)},${json(evidence)},${evidence.year ? Number(evidence.year) : 'NULL'})`)
        return id
      }
      const showing = (filmId: string, slug: string, day: string, clock: string, run: Record<string, unknown>, formats: string[] = ['Format.Projection.Digital']) => {
        const category = run.run === 'rerun' ? 'olderFilm' : run.run === 'firstRun' ? 'newRelease' : 'unclassified'
        db.sql(`INSERT INTO cinema_screenings (id,venue_id,film_id,source_key,identity_strength,local_date,source_local_start,starts_utc,formats,booking_url,release_category,category_evidence,confirmation,last_seen_utc) VALUES (${sql(randomUUID())},${sql(venue(slug).id)},${sql(filmId)},${sql(`${label}:${randomUUID()}`)},'opaque',${sql(day)},${sql(`${day}T${clock}:00`)},${sql(naive(london(day, clock)))},${json(formats)},${sql(booking(slug, clock))},${sql(category)},${json(run)},'confirmed',now() AT TIME ZONE 'utc')`)
      }
      const linked = (tmdbId: number, poster: string, year: number) => ({ tmdbId, posterPath: poster, year, identity: { outcome: 'linked', reason: '', corroboration: ['the director'], others: [] } })
      const firstRun = { run: 'firstRun', runReason: 'UK release 6 Nov 2026 · first run' }
      const rerun = { run: 'rerun', runReason: 'UK release 1977 · rerun' }
      // The phone's today: one film at five cinemas, the Omniplex among them, and one at GFT.
      for (const [slug, clock, formats] of [
        ['cineworld-silverburn', '09:30', ['Format.Projection.Digital']],
        ['cineworld-silverburn', '13:00', ['Format.Projection.3d']],
        ['science-centre-imax', '15:45', ['IMAX']],
        ['omniplex-glasgow-renfrew-street', '18:15', ['maxx']],
        ['vue-st-enoch', '19:00', []],
        ['odeon-braehead', '20:30', ['Format.Projection.Digital']],
      ] as const) {
        showing(film('lantern', slug, LANTERN, 'verified', linked(9_300_001, '/ae5-lantern.jpg', 2026)), slug, plus(1), clock, firstRun, [...formats])
      }
      showing(film('harbour', 'gft', HARBOUR, 'verified', linked(9_300_002, '/ae5-harbour.jpg', 1976)), 'gft', plus(1), '17:00', rerun)
      showing(film('harbour', 'vue-st-enoch', HARBOUR, 'verified', linked(9_300_002, '/ae5-harbour.jpg', 1976)), 'vue-st-enoch', plus(2), '18:00', rerun, [])
      const waiting = { identity: { outcome: 'unlinked', reason: 'not yet looked up on TMDB', corroboration: [], others: [] } }
      showing(film('mystery', 'odeon-glasgow-quay', 'Mystery Preview Night', 'unverified', waiting), 'odeon-glasgow-quay', plus(1), '19:30', {})
      showing(film('tempest', 'odeon-glasgow-quay', 'National Theatre Live: The Tempest', 'event', { identity: { outcome: 'event', reason: 'a live or staged event, not a film', corroboration: [], others: [] } }), 'odeon-glasgow-quay', plus(1), '19:00', {})
      // Day 3, past GFT's and Vue's lists: a film at two other cinemas. Day 4: nothing anywhere.
      for (const [slug, clock] of [['everyman-glasgow', '20:00'], ['odeon-east-kilbride', '18:00']] as const) {
        showing(film('northern', slug, NORTHERN, 'verified', linked(9_300_003, '/ae5-northern.jpg', 2026)), slug, plus(3), clock, firstRun)
      }
      await use({ plus, morning: london(plus(1), '10:00'), evening: london(plus(1), '21:00') })
    } finally {
      db.sql(`DELETE FROM cinema_films WHERE source_key LIKE ${sql(`${label}:%`)}; DELETE FROM cinema_coverage WHERE source_update_label=${sql(label)};
        INSERT INTO cinema_coverage SELECT * FROM json_populate_recordset(NULL::cinema_coverage, ${sql(kept)}::json) ON CONFLICT DO NOTHING;
        UPDATE cinema_venues v SET collection_enabled=(${sql(enabled)}::json->>v.slug)::boolean`)
    }
  },
})

async function phone(signedIn: (person: 'Craig' | 'Mark') => Promise<Session>, person: 'Craig' | 'Mark', theme: 'light' | 'dark', at: Date): Promise<Session> {
  const session = await signedIn(person)
  await session.page.setViewportSize({ width: 375, height: 812 })
  await session.context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
  await posters(session.page)
  await session.page.clock.install({ time: at })
  return session
}

const noSidewaysScroll = (session: Session) => session.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

test('AE5 At the cinema opens on All days (AF3), a day shows each film’s times by cinema with past ones gone, the strip held on scroll, at 375 px in both themes for both people', async ({ signedIn, week }, testInfo) => {
  for (const person of ['Craig', 'Mark'] as const) {
    for (const theme of ['light', 'dark'] as const) {
      const session = await phone(signedIn, person, theme, week.morning)
      const { page } = session
      const name = `${person.toLowerCase()}-${theme}`
      await page.goto('/movie-night/cinema')
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      const strip = page.getByRole('group', { name: 'Day' })
      // AF3 (#372): All films, All days with nothing in the address, All days leading the strip.
      await expect(strip.getByRole('button').first()).toHaveText('All days')
      await expect(strip.getByRole('button', { name: 'All days', exact: true })).toHaveAttribute('aria-pressed', 'true')
      await expect(page.getByRole('region', { name: 'This week', exact: true })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(`ae5-all-days-${name}-375.png`) })
      const today = strip.getByRole('button', { name: dayLabel(week.plus(1)), exact: true })
      await expect(today).toHaveText('Today')
      await today.click()
      await expect(today).toHaveAttribute('aria-pressed', 'true')
      await expect(page).toHaveURL(new RegExp(`\\?day=${week.plus(1)}$`))
      // The strip leads, before the run and the cinemas.
      expect(await strip.evaluate(element => Boolean(element.compareDocumentPosition(document.querySelector('[role="group"][aria-label="Run"]') as Node) & Node.DOCUMENT_POSITION_FOLLOWING))).toBe(true)

      const day = page.getByRole('region', { name: dayLabel(week.plus(1)), exact: true })
      await expect(day.getByRole('article')).toHaveCount(2)
      // The widest first: five cinemas, then one.
      await expect(day.getByRole('article').first()).toHaveAccessibleName(LANTERN)
      const lantern = day.getByRole('article', { name: LANTERN })
      await expect(lantern.getByRole('list', { name: /^Times at / })).toHaveCount(5)
      // 09:30 started before 10:00, so 13:00 is all Silverburn has left; its chip names the 3D.
      const silverburn = lantern.getByRole('list', { name: 'Times at Cineworld Glasgow Silverburn' })
      await expect(silverburn.getByRole('listitem')).toHaveCount(1)
      await expect(silverburn.getByRole('link', { name: 'Book 13:00 3D at Cineworld Glasgow Silverburn' })).toHaveAttribute('href', booking('cineworld-silverburn', '13:00'))
      // The tenth cinema, its big screen named; every chip opens the cinema's page outside the app.
      await expect(lantern.getByRole('link', { name: 'Book 18:15 MAXX at Omniplex Glasgow - Renfrew Street' })).toHaveAttribute('href', booking('omniplex-glasgow-renfrew-street', '18:15'))
      await expect(lantern.getByRole('link', { name: 'Book 20:30 at ODEON Braehead' })).toBeVisible()
      for (const link of await lantern.getByRole('link', { name: /^Book / }).all()) {
        await expect(link).toHaveAttribute('target', '_blank')
        await expect(link).toHaveAttribute('rel', 'noopener noreferrer')
      }
      await expect(day.getByRole('article', { name: HARBOUR })).toContainText('Rerun')
      // Listings and events stay folded until opened, each with its count.
      for (const [section, count] of [['Not matched to a film yet', 1], ['Events and double bills', 1]] as const) {
        const region = page.getByRole('region', { name: section, exact: true })
        await expect(region.locator('details')).not.toHaveAttribute('open', '')
        await expect(region.getByRole('heading')).toHaveText(`${section} · ${String(count)}`)
      }
      expect(await noSidewaysScroll(session)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ae5-today-${name}-375.png`) })

      // The strip stays at the top while the day scrolls under it.
      const main = page.locator('#main-content')
      const bar = strip.locator('..')
      const top = async () => ((await bar.boundingBox())?.y ?? 0) - ((await main.boundingBox())?.y ?? 0)
      expect(await top()).toBeGreaterThan(20)
      await main.evaluate(element => { element.scrollTop = element.scrollHeight })
      expect(await main.evaluate(element => element.scrollTop)).toBeGreaterThan(0)
      await expect.poll(top).toBeLessThanOrEqual(1)
      await page.screenshot({ path: testInfo.outputPath(`ae5-scrolled-${name}-375.png`) })
      await main.evaluate(element => { element.scrollTop = 0 })

      // All / None over the ten.
      await page.getByText(/^Cinemas · all 10/).click()
      await expect(page.getByRole('checkbox')).toHaveCount(10)
      await page.getByRole('button', { name: 'None', exact: true }).click()
      await expect(page.getByText('Select at least one cinema.', { exact: true })).toBeVisible()
      await expect(page).toHaveURL(/cinema=none$/)
      await expect(page.getByRole('checkbox', { checked: true })).toHaveCount(0)
      await page.screenshot({ path: testInfo.outputPath(`ae5-none-${name}-375.png`) })
      await page.getByRole('button', { name: 'All', exact: true }).click()
      await expect(page.getByRole('checkbox', { checked: true })).toHaveCount(10)
      await expect(page).toHaveURL(new RegExp(`/movie-night/cinema\\?day=${week.plus(1)}$`))
      await page.getByText(/^Cinemas · all 10/).click()

      // Opened, the listing and the event read as before.
      await expect((await unfold(page, 'Not matched to a film yet')).getByRole('article', { name: 'Mystery Preview Night' })).toContainText('Not matched yet · ODEON Quay')
      await expect((await unfold(page, 'Events and double bills')).getByRole('article', { name: 'National Theatre Live: The Tempest' })).toBeVisible()
      await page.getByRole('region', { name: 'Events and double bills', exact: true }).scrollIntoViewIfNeeded()
      await page.screenshot({ path: testInfo.outputPath(`ae5-unfolded-${name}-375.png`) })
      await session.context.close()
    }
  }
})

test('AE5 a day picked stays in the address, an empty day says so, a day past two cinemas’ lists shows the rest, and tomorrow follows a finished today', async ({ signedIn, week }, testInfo) => {
  for (const [person, theme] of [['Mark', 'light'], ['Craig', 'dark']] as const) {
    const session = await phone(signedIn, person, theme, week.morning)
    const { page } = session
    const name = `${person.toLowerCase()}-${theme}`
    await page.goto('/movie-night/cinema')
    const strip = page.getByRole('group', { name: 'Day' })
    await expect(strip.getByRole('button', { name: 'All days', exact: true })).toHaveAttribute('aria-pressed', 'true')

    // Day 3: GFT and Vue list only to day 2, so its film shows at the two cinemas that list it.
    await strip.getByRole('button', { name: dayLabel(week.plus(3)), exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`\\?day=${week.plus(3)}$`))
    const third = page.getByRole('region', { name: dayLabel(week.plus(3)), exact: true })
    const northern = third.getByRole('article', { name: NORTHERN })
    await expect(northern.getByRole('list', { name: /^Times at / })).toHaveCount(2)
    await expect(page.getByRole('region', { name: 'How far ahead cinemas list' })).toContainText(`GFT, Vue St Enoch: listed only to ${dayLabel(week.plus(2))}`)
    // A film's page and back keeps the day.
    await filmLink(northern, NORTHERN).click()
    await expect(page.getByRole('heading', { name: NORTHERN, level: 1 })).toBeVisible()
    await page.goBack()
    await expect(page).toHaveURL(new RegExp(`\\?day=${week.plus(3)}$`))
    await expect(third.getByRole('article', { name: NORTHERN })).toBeVisible()

    // Day 4 has nothing at any cinema: greyed in the strip, and said so when picked.
    const empty = strip.getByRole('button', { name: dayLabel(week.plus(4)), exact: true })
    await expect(empty).toHaveAttribute('title', 'Nothing showing')
    await expect(strip.getByRole('button', { name: dayLabel(week.plus(3)), exact: true })).not.toHaveAttribute('title', 'Nothing showing')
    await empty.click()
    await expect(page.getByText('Nothing listed for this choice', { exact: true })).toBeVisible()
    expect(await noSidewaysScroll(session)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath(`ae5-empty-day-${name}-375.png`) })

    // Today is named in the address too, since every day at once is the default (AF3).
    await strip.getByRole('button', { name: dayLabel(week.plus(1)), exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`\\?day=${week.plus(1)}$`))
    await expect(page.getByRole('region', { name: dayLabel(week.plus(1)), exact: true }).getByRole('article', { name: LANTERN })).toBeVisible()
    // 21:00 with the page left open: every time today has started, so the view says so.
    await page.clock.fastForward(week.evening.getTime() - week.morning.getTime())
    await expect(page.getByText('Nothing more today', { exact: true })).toBeVisible()
    await expect(page.getByRole('article', { name: LANTERN })).toHaveCount(0)
    await page.screenshot({ path: testInfo.outputPath(`ae5-done-today-${name}-375.png`) })
    await page.getByRole('button', { name: 'See tomorrow' }).click()
    await expect(page).toHaveURL(new RegExp(`\\?day=${week.plus(2)}$`))
    await expect(page.getByRole('region', { name: dayLabel(week.plus(2)), exact: true }).getByRole('article', { name: HARBOUR })).toBeVisible()
    await session.context.close()
  }
})
