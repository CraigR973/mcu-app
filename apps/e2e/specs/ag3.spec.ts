import { posters } from '../support/cinema-view.ts'
import { expect, test } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
/** "Wed 11 Nov", as the app writes a day. */
const dayLabel = (day: string) => `${WEEKDAYS[new Date(`${day}T12:00:00Z`).getUTCDay()]} ${Number(day.slice(8))} ${MONTHS[Number(day.slice(5, 7)) - 1]}`

// AG3 (CT52-01, UX54-01, UX54-02): a cinema not read is said at the top of At the cinema and under
// Home's strip heading, and a phone that gets no notifications is said on its own person's Home.
// Two ODEONs read well on 11 Nov and failed since, as four did; every other cinema was read this
// morning. Rows go only into the harness's disposable Postgres and are put back afterwards.
test('AG3 a cinema not read, and a phone with no notifications, are said where each person looks, at 375 px in both themes', async ({ signedIn, db }, testInfo) => {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
  const part = (type: Intl.DateTimeFormatPartTypes) => parts.find(item => item.type === type)?.value
  const today = `${part('year')}-${part('month')}-${part('day')}`
  const sixDaysAgo = new Date(Date.now() - 6 * 86400000)
  const fortnight = `local_date BETWEEN ${sql(today)}::date AND ${sql(today)}::date + 13`
  const kept = db.scalar(`SELECT coalesce(json_agg(c), '[]'::json)::text FROM cinema_coverage c WHERE ${fortnight}`)
  const enabled = db.scalar(`SELECT json_object_agg(slug, collection_enabled)::text FROM cinema_venues`)
  const live = db.scalar(`SELECT coalesce(json_agg(id), '[]'::json)::text FROM push_subscriptions WHERE revoked_at_utc IS NULL`)
  const readOn = (sixDaysAgo.toISOString().slice(0, 10))
  try {
    db.sql(`DELETE FROM cinema_coverage WHERE ${fortnight};
      UPDATE cinema_venues SET collection_enabled=true;
      INSERT INTO cinema_coverage (id,venue_id,local_date,status,observed,complete,last_attempt_utc,last_success_utc)
      SELECT gen_random_uuid(), v.id, d::date,
        CASE WHEN v.slug IN ('odeon-braehead','odeon-kilmarnock') THEN 'failed' ELSE 'healthy' END,
        v.slug NOT IN ('odeon-braehead','odeon-kilmarnock'), true,
        now() AT TIME ZONE 'utc',
        CASE WHEN v.slug IN ('odeon-braehead','odeon-kilmarnock') THEN ${sql(sixDaysAgo.toISOString().slice(0, 19))}::timestamp ELSE now() AT TIME ZONE 'utc' END
      FROM cinema_venues v, generate_series(${sql(today)}::date, ${sql(today)}::date + 13, interval '1 day') d;
      UPDATE push_subscriptions SET revoked_at_utc=now() AT TIME ZONE 'utc', revoked_reason='ag3-e2e' WHERE revoked_at_utc IS NULL`)
    for (const person of ['Craig', 'Mark'] as const) {
      for (const theme of ['light', 'dark'] as const) {
        const { context, page } = await signedIn(person)
        await posters(page)
        await page.setViewportSize({ width: 375, height: 812 })
        await context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
        const line = `2 cinemas not read since ${dayLabel(readOn)}.`

        // At the cinema: the line sits with the filters, at the top, before any film.
        await page.goto('/movie-night/cinema')
        const filters = page.getByRole('group', { name: 'Filters' })
        await expect(filters.getByText(line)).toBeVisible()
        expect(await filters.getByText(line).evaluate(element => element.getBoundingClientRect().top < innerHeight)).toBe(true)
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        await page.screenshot({ path: testInfo.outputPath(`ag3-cinema-${person.toLowerCase()}-${theme}-375.png`) })

        // Home: under the strip's heading, and the person's own phone, said to them.
        await page.goto('/dashboard')
        await expect(page.getByRole('link', { name: /This phone is not getting notifications/ })).toBeVisible()
        await expect(page.getByRole('link', { name: /This phone is not getting notifications/ })).toHaveAttribute('href', '/settings?tab=notifications')
        await expect(page.getByText(line)).toBeVisible()
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        await page.getByRole('link', { name: /This phone is not getting notifications/ }).scrollIntoViewIfNeeded()
        await page.screenshot({ path: testInfo.outputPath(`ag3-home-${person.toLowerCase()}-${theme}-375.png`), fullPage: true })
        await context.close()
      }
    }
  } finally {
    db.sql(`DELETE FROM cinema_coverage WHERE ${fortnight};
      INSERT INTO cinema_coverage SELECT * FROM json_populate_recordset(NULL::cinema_coverage, ${sql(kept)}::json) ON CONFLICT DO NOTHING;
      UPDATE cinema_venues v SET collection_enabled=(${sql(enabled)}::json->>v.slug)::boolean;
      UPDATE push_subscriptions SET revoked_at_utc=NULL, revoked_reason=NULL WHERE id IN (SELECT json_array_elements_text(${sql(live)}::json)::uuid)`)
  }
})
