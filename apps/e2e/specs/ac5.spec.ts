import { randomUUID } from 'node:crypto'
import type { Page } from '@playwright/test'
import { pushesTo, registerDevice, type Device } from '../support/push.ts'
import { test as base, expect } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const json = (value: unknown) => `${sql(JSON.stringify(value))}::jsonb`

/** A TMDB id no other case uses, and the film AC3 would have linked it to at two cinemas. */
const TMDB = 9_300_001
const TITLE = 'AC5 Wild Horse Nine'
const KEY = `tmdb-${TMDB}`

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const LONDON = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })

/** A showing's time as the cinema (and so the app) writes it: "Tue 10 Nov", "20:10". */
function london(iso: string): { day: string; clock: string } {
  const parts = LONDON.formatToParts(new Date(iso))
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value ?? ''
  const date = `${part('year')}-${part('month')}-${part('day')}`
  const weekday = WEEKDAYS[new Date(`${date}T12:00:00Z`).getUTCDay()]
  return { day: `${weekday} ${Number(part('day'))} ${MONTHS[Number(part('month')) - 1]}`, clock: `${part('hour')}:${part('minute')}` }
}

interface Time { id: string; at: string; day: string; clock: string }
type Fixture = { quay: Time; silverburn: Time; markId: string }

// AC5 (#345): the checkpoint's worked example, at the cinemas it named. Wild Horse Nine (here
// under a name no other case uses) at ODEON Glasgow Quay tomorrow at 20:10 and at Cineworld
// Glasgow Silverburn the day after at 20:00, both linked to one TMDB film as AC3 links them, with
// a current listing behind each so Check tickets shows. Rows go only into the harness's
// disposable Postgres; every screen reads them through the real API.
const test = base.extend<{ cinema: Fixture }>({
  cinema: async ({ db, api }, use) => {
    const label = `ac5-e2e:${randomUUID()}`
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
    const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value
    const today = `${part('year')}-${part('month')}-${part('day')}`
    const plus = (days: number) => new Date(Date.parse(`${today}T12:00:00Z`) + days * 86400000).toISOString().slice(0, 10)
    const enabled = db.scalar(`SELECT json_object_agg(slug, collection_enabled)::text FROM cinema_venues`)
    const venues = "('odeon-glasgow-quay','cineworld-silverburn')"
    db.sql(`UPDATE cinema_venues SET collection_enabled=true WHERE slug IN ${venues};
      INSERT INTO cinema_coverage (id,venue_id,local_date,status,observed,complete,last_attempt_utc,last_success_utc,source_update_label)
      SELECT gen_random_uuid(), v.id, d::date, 'healthy', true, true, now() AT TIME ZONE 'utc', now() AT TIME ZONE 'utc', ${sql(label)}
      FROM cinema_venues v, generate_series(${sql(today)}::date, ${sql(today)}::date + 13, interval '1 day') d
      WHERE v.slug IN ${venues} ON CONFLICT (venue_id, local_date) DO NOTHING`)
    const showing = (slug: string, day: string, at: string, booking: string): Time => {
      const venue = JSON.parse(db.scalar(`SELECT json_build_object('id',id,'source',source)::text FROM cinema_venues WHERE slug=${sql(slug)}`)) as { id: string; source: string }
      const film = randomUUID()
      db.sql(`INSERT INTO cinema_films (id,source,source_key,title,identity_status,evidence,original_year)
        VALUES (${sql(film)},${sql(venue.source)},${sql(`${label}:${slug}`)},${sql(TITLE)},'verified',${json({ tmdbId: TMDB, posterPath: '/ac5-horse.jpg', year: 2026 })},2026)`)
      const id = randomUUID()
      const starts = `${day}T${at}:00`
      db.sql(`INSERT INTO cinema_screenings (id,venue_id,film_id,source_key,identity_strength,local_date,source_local_start,starts_utc,formats,booking_url,release_category,category_evidence,confirmation,last_seen_utc)
        VALUES (${sql(id)},${sql(venue.id)},${sql(film)},${sql(`${label}:${id}`)},'opaque',${sql(day)},${sql(starts)},${sql(starts)},${json(['Format.Projection.Digital'])},${sql(booking)},'newRelease',${json({ run: 'firstRun', runReason: 'UK release 30 Oct 2026 · first run' })},'confirmed',now() AT TIME ZONE 'utc')`)
      return { id, at: `${starts}Z`, ...london(`${starts}Z`) }
    }
    const quay = showing('odeon-glasgow-quay', plus(1), '20:10', 'https://www.odeon.co.uk/ticketing/seat-picker/?showtimeId=ac5')
    const silverburn = showing('cineworld-silverburn', plus(2), '20:00', 'https://web.cineworld.co.uk/order/showtimes/ac5')
    const markId = db.scalar("SELECT id FROM profiles WHERE display_name='Mark'")
    // Both people hear about trips as they happen: no digest, no quiet hours.
    const kept: Record<string, Record<string, unknown>> = {}
    for (const person of ['Craig', 'Mark'] as const) {
      const who = await api(person)
      kept[person] = await who.get<Record<string, unknown>>('/notifications/preferences')
      await who.put('/notifications/preferences', { movieNightEnabled: true, digestMode: false, clearQuietHours: true })
    }
    try {
      await use({ quay, silverburn, markId })
    } finally {
      for (const person of ['Craig', 'Mark'] as const) {
        const old = kept[person]
        await (await api(person)).put('/notifications/preferences', {
          movieNightEnabled: old.movieNightEnabled, digestMode: old.digestMode,
          ...(old.quietHoursStart ? { quietHoursStart: old.quietHoursStart, quietHoursEnd: old.quietHoursEnd } : { clearQuietHours: true }),
        })
      }
      db.sql(`DELETE FROM cinema_trips WHERE film_key=${sql(KEY)}; DELETE FROM cinema_films WHERE source_key LIKE ${sql(`${label}:%`)};
        DELETE FROM cinema_coverage WHERE source_update_label=${sql(label)};
        UPDATE cinema_venues v SET collection_enabled=(${sql(enabled)}::json->>v.slug)::boolean`)
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
      body: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 300"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="hsl(${hue} 45% 38%)"/><stop offset="1" stop-color="hsl(${(hue + 40) % 360} 50% 16%)"/></linearGradient></defs><rect width="200" height="300" fill="url(#g)"/><text x="100" y="250" fill="white" font-family="Georgia" font-size="22" text-anchor="middle">${name.replace(/^ac5-|\.jpg$/g, '')}</text></svg>`,
    })
  })
}

type SignedIn = (person: 'Craig' | 'Mark') => Promise<{ context: import('@playwright/test').BrowserContext; page: Page }>
async function phone(signedIn: SignedIn, person: 'Craig' | 'Mark', theme: string): Promise<Page> {
  const session = await signedIn(person)
  await session.page.setViewportSize({ width: 375, height: 812 })
  await session.context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
  await posters(session.page)
  return session.page
}

const noSidewaysScroll = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

/** A time chip in a picker: "20:10 at ODEON Glasgow Quay, Tomorrow · Tue 10 Nov". */
const timeChip = (scope: Page | ReturnType<Page['getByRole']>, time: Time, venue: string) =>
  scope.getByRole('button', { name: new RegExp(`^${time.clock} at ${venue}, (Today · |Tomorrow · )?${time.day}$`) })

/** The one push to this device with this title, once it has arrived. */
async function pushed(device: Device, title: string) {
  await expect.poll(() => pushesTo(device).map(p => p.title), { message: `a push "${title}"` }).toContain(title)
  const found = pushesTo(device).filter(p => p.title === title)
  expect(found).toHaveLength(1)
  return found[0]
}

for (const theme of ['light', 'dark'] as const) {
  test(`Craig proposes, Mark suggests another time, Craig accepts, then cancels — 375px, ${theme}`, async ({ signedIn, api, cinema }, testInfo) => {
    const shot = async (page: Page, name: string) => {
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      expect(await noSidewaysScroll(page)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ac5-${name}-${theme}-375.png`), fullPage: true })
    }
    const craigPhone = await registerDevice(await api('Craig'), `ac5-craig-${theme}`)
    const markPhone = await registerDevice(await api('Mark'), `ac5-mark-${theme}`)
    const craig = await phone(signedIn, 'Craig', theme)
    const mark = await phone(signedIn, 'Mark', theme)
    const { quay, silverburn } = cinema

    // Craig starts where #345 §6 says one starts: Movie night → Plan a cinema trip → At the
    // cinema → the film's page (light), or the film's page itself (dark).
    if (theme === 'light') {
      await craig.goto('/movie-night')
      await craig.getByRole('region', { name: 'Plan a cinema trip' }).getByRole('link', { name: 'See what’s on' }).click()
      await craig.locator(`a[href="/movie-night/cinema/${KEY}"]`).first().click()
    } else {
      await craig.goto(`/movie-night/cinema/${KEY}`)
    }
    await expect(craig.getByRole('heading', { level: 1, name: TITLE })).toBeVisible()
    await craig.getByRole('button', { name: 'Propose a trip' }).click()
    const sheet = craig.getByRole('dialog', { name: 'Propose a trip' })
    await timeChip(sheet, quay, 'ODEON Glasgow Quay').click()
    const markBox = sheet.getByRole('checkbox', { name: 'Mark' })
    await expect(markBox).not.toBeChecked()
    await markBox.check()
    await shot(craig, 'craig-propose')
    await sheet.getByRole('button', { name: 'Send invitations' }).click()
    await expect(craig).toHaveURL(/\/movie-night\/trips\/[0-9a-f-]{36}$/)
    const tripPath = new URL(craig.url()).pathname
    await expect(craig.getByText(`${quay.day} · ${quay.clock} · ODEON Glasgow Quay`)).toBeVisible()
    await expect(craig.getByRole('link', { name: 'Check tickets at ODEON Glasgow Quay' })).toBeVisible()
    await expect(craig.getByRole('region', { name: 'Who’s going' })).toContainText('1 going · 1 no reply yet')
    await shot(craig, 'craig-trip-proposed')

    // Mark is told by push, and Home's Needs you asks him until he replies.
    const invite = await pushed(markPhone, 'Craig invited you to the cinema')
    expect(invite.body).toBe(`${TITLE}, ${quay.day} at ${quay.clock}, ODEON Glasgow Quay. Going, not going, or another time?`)
    expect(invite.url).toBe(tripPath)
    await mark.goto('/')
    const needs = mark.getByRole('region', { name: /Needs you/ })
    const item = needs.getByRole('link', { name: new RegExp(`Craig invited you: ${TITLE}, ${quay.day} ${quay.clock}`) })
    await expect(item).toBeVisible()
    await shot(mark, 'mark-home-invited')
    await item.click()
    await expect(mark).toHaveURL(new RegExp(`${tripPath}$`))
    await expect(mark.getByRole('heading', { level: 1, name: TITLE })).toBeVisible()
    await shot(mark, 'mark-trip-invited')

    // Mark suggests another time; only Craig is told.
    await mark.getByRole('region', { name: 'Your reply' }).getByRole('button', { name: 'Another time' }).click()
    await timeChip(mark, silverburn, 'Cineworld Glasgow Silverburn').click()
    await mark.getByRole('button', { name: 'Suggest this time' }).click()
    await expect(mark.getByRole('region', { name: 'Who’s going' })).toContainText(`Suggests ${silverburn.day} ${silverburn.clock} · Cineworld Glasgow Silverburn`)
    const suggestion = await pushed(craigPhone, 'Mark suggests another time')
    expect(suggestion.body).toBe(`${TITLE}: ${silverburn.day} at ${silverburn.clock}, Cineworld Glasgow Silverburn, instead of ${quay.day} at ${quay.clock}. Open it to accept or keep your time.`)
    expect(suggestion.url).toBe(tripPath)

    // Craig sees it waiting in Needs you, opens the trip and accepts it.
    await craig.goto('/')
    await craig.getByRole('region', { name: /Needs you/ }).getByRole('link', { name: new RegExp(`Mark suggests another time for ${TITLE}`) }).click()
    await expect(craig).toHaveURL(new RegExp(`${tripPath}$`))
    await shot(craig, 'craig-trip-suggestion')
    await craig.getByRole('button', { name: 'Accept this time' }).click()
    await expect(craig.getByText(`${silverburn.day} · ${silverburn.clock} · Cineworld Glasgow Silverburn`)).toBeVisible()
    const accepted = await pushed(markPhone, 'Craig accepted your time')
    expect(accepted.body).toBe(`${TITLE}, ${silverburn.day} at ${silverburn.clock}, Cineworld Glasgow Silverburn. You're down as going.`)

    // Mark sees the move and that he is going; Home's top slot holds the trip.
    await mark.reload()
    await expect(mark.getByText(`${silverburn.day} · ${silverburn.clock} · Cineworld Glasgow Silverburn`)).toBeVisible()
    await expect(mark.getByRole('region', { name: 'Your reply' }).getByRole('button', { name: 'Going', exact: true })).toHaveAttribute('aria-pressed', 'true')
    await expect(mark.getByRole('region', { name: 'Who’s going' })).toContainText('2 going')
    await shot(mark, 'mark-trip-going')
    await mark.goto('/')
    await expect(mark.getByRole('link', { name: `Next: ${TITLE}, ${silverburn.day} ${silverburn.clock} at Cineworld Glasgow Silverburn, with Craig` })).toBeVisible()
    await shot(mark, 'mark-home-next')

    // Craig cancels; Mark, who is going, is told, and the trip folds into Past trips.
    await craig.getByRole('button', { name: 'Cancel trip' }).click()
    await craig.getByRole('button', { name: 'Cancel the trip' }).click()
    await expect(craig.getByText('You cancelled this trip.')).toBeVisible()
    const cancelled = await pushed(markPhone, 'Cinema trip cancelled')
    expect(cancelled.body).toBe(`Craig cancelled ${TITLE} on ${silverburn.day} at ${silverburn.clock}, Cineworld Glasgow Silverburn.`)
    await mark.goto(tripPath)
    await expect(mark.getByText('Craig cancelled this trip.')).toBeVisible()
    await expect(mark.getByRole('region', { name: 'Your reply' })).toHaveCount(0)
    for (const [who, page] of [['craig', craig], ['mark', mark]] as const) {
      await page.goto('/movie-night')
      const trips = page.getByRole('region', { name: 'Cinema trips' })
      const fold = trips.locator('details').filter({ hasText: /^Past trips \(\d+\)/ })
      await expect(fold).not.toHaveAttribute('open', '')
      await fold.getByText(/^Past trips/).click()
      await expect(fold.locator(`a[href="${tripPath}"]`)).toBeVisible()
      await shot(page, `${who}-movie-night`)
    }
  })
}

test('a time the cinema withdraws is flagged on the trip, and the organiser is asked to act', async ({ signedIn, api, db, cinema }, testInfo) => {
  const trip = await (await api('Craig')).post<{ id: string }>('/cinema-trips', {
    clientRequestId: randomUUID(), filmKey: KEY, showingId: cinema.quay.id, inviteeIds: [cinema.markId],
  })
  db.sql(`UPDATE cinema_screenings SET confirmation='withdrawn' WHERE id=${sql(cinema.quay.id)}`)
  for (const person of ['Craig', 'Mark'] as const) {
    for (const theme of ['light', 'dark']) {
      const page = await phone(signedIn, person, theme)
      await page.goto(`/movie-night/trips/${trip.id}`)
      await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
      const line = person === 'Craig' ? 'ODEON Glasgow Quay no longer lists this time. Pick another time or cancel.' : 'ODEON Glasgow Quay no longer lists this time.'
      await expect(page.getByRole('status').filter({ hasText: 'no longer lists this time' })).toHaveText(line)
      await expect(page.getByRole('link', { name: /Check tickets/ })).toHaveCount(0)
      expect(await noSidewaysScroll(page)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ac5-withdrawn-${person.toLowerCase()}-${theme}-375.png`), fullPage: true })
      if (person === 'Craig') {
        await page.goto('/')
        await expect(page.getByRole('region', { name: /Needs you/ }).getByRole('link', { name: new RegExp(`ODEON Glasgow Quay no longer lists your ${TITLE} time`) })).toBeVisible()
      }
    }
  }
})
