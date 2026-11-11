import { randomUUID } from 'node:crypto'
import { expect, test } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const noSidewaysScroll = (page: import('@playwright/test').Page) =>
  page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)

// AE10 (#355): movie night that reaches a match, against the real API on Postgres. Craig starts
// a night for Mark with filters (A, B); Mark sees how far Craig has got (C); they add the same
// film, and the match says where the disc is and logs it for both (D). A film of the spec's own,
// a 4K horror under two hours on the Lounge's shelf, is the match; it and its viewings are
// removed for good after, so later cases' counts hold. Rows go only into the harness's
// disposable Postgres.
test('AE10 a night started for Mark reaches a match that says the shelf and logs it for both, at 375 px', async ({ signedIn, db }, testInfo) => {
  const film = { id: randomUUID(), title: 'Matinee For Two' }
  db.sql(`INSERT INTO movies (id,title,original_title,year,media_type,runtime_minutes,genres) VALUES (${sql(film.id)},${sql(film.title)},${sql(film.title)},2004,'film',98,'[{"id":27,"name":"Horror"}]'::jsonb);
    INSERT INTO collection_items (id,movie_id,formats,location,condition) VALUES (${sql(randomUUID())},${sql(film.id)},'["4k_uhd"]'::jsonb,'Lounge','good');`)
  let nightId: string | null = null
  try {
    const craig = await signedIn('Craig')
    await craig.page.setViewportSize({ width: 375, height: 812 })
    await craig.page.goto('/movie-night')
    // A: who is watching, nobody ticked until ticked. B: the filters in place of the year box.
    await expect(craig.page.getByText('Nothing older than')).toHaveCount(0)
    await craig.page.getByRole('checkbox', { name: 'Mark' }).check()
    await craig.page.getByRole('checkbox', { name: 'Under two hours' }).check()
    await craig.page.getByRole('checkbox', { name: '4K' }).check()
    await craig.page.getByRole('combobox', { name: 'Genre' }).selectOption('Horror')
    expect(await noSidewaysScroll(craig.page)).toBe(true)
    await craig.page.screenshot({ path: testInfo.outputPath('ae10-start-craig-light-375.png'), fullPage: true })
    await craig.page.getByRole('button', { name: 'Start and send to Mark' }).click()
    await expect(craig.page).toHaveURL(/\/movie-night\/[0-9a-f-]{36}$/)
    nightId = new URL(craig.page.url()).pathname.split('/').pop() ?? null
    await expect(craig.page.getByText('Sent to Mark')).toBeVisible()

    // B: ten at most, each saying why, under the filters it started with.
    const shelf = craig.page.getByRole('region', { name: /From the shelf/ })
    await expect(shelf.getByRole('list', { name: 'Started with' })).toContainText('Under two hours')
    await expect(shelf.getByRole('list', { name: 'Started with' })).toContainText('Horror')
    expect(await shelf.getByRole('button', { name: /^Add / }).count()).toBeLessThanOrEqual(10)
    const row = shelf.getByRole('listitem').filter({ hasText: film.title })
    await expect(row).toContainText('In neither diary')
    await row.getByRole('button', { name: `Add ${film.title}` }).click()
    await expect(shelf.getByText("You've added 1")).toBeVisible()

    // C: Mark sees how far Craig has got, never which film.
    const mark = await signedIn('Mark')
    await mark.page.setViewportSize({ width: 375, height: 812 })
    await mark.page.goto(`/movie-night/${String(nightId)}`)
    await expect(mark.page.getByRole('list', { name: 'How far everyone has got' })).toContainText('Craig has added 1')
    await expect(mark.page.getByRole('button', { name: `Add ${film.title}` })).toHaveAttribute('aria-pressed', 'false')
    expect(await noSidewaysScroll(mark.page)).toBe(true)
    await mark.page.screenshot({ path: testInfo.outputPath('ae10-progress-mark-light-375.png') })

    // D: the match says where the disc is and how long, and logs it for both, once.
    await mark.page.getByRole('button', { name: `Add ${film.title}` }).click()
    const card = mark.page.getByRole('status').filter({ hasText: "It's a match" })
    await expect(card).toBeVisible()
    await expect(card).toContainText('1h 38m')
    await expect(card.getByRole('list', { name: 'Where the disc is' })).toContainText('Lounge')
    await card.getByRole('button', { name: 'Log it for both of us' }).click()
    await expect(card).toContainText('Logged for both of you')
    expect(db.scalar(`SELECT count(*) FROM watch_log WHERE movie_id = ${sql(film.id)} AND letterboxd_viewing_id IS NULL AND deleted_at IS NULL`)).toBe('2')
    await card.scrollIntoViewIfNeeded()
    await mark.page.screenshot({ path: testInfo.outputPath('ae10-match-mark-light-375.png') })

    // The same night in the dark theme, from Craig's side: the match remembered, already logged.
    const dark = await signedIn('Craig')
    await dark.page.setViewportSize({ width: 375, height: 812 })
    await dark.context.addInitScript(value => localStorage.setItem('mcu-theme', value), 'dark')
    await dark.page.goto(`/movie-night/${String(nightId)}`)
    await expect(dark.page.getByRole('status').filter({ hasText: "It's a match" })).toContainText('Logged for both of you')
    expect(await noSidewaysScroll(dark.page)).toBe(true)
    await dark.page.screenshot({ path: testInfo.outputPath('ae10-match-craig-dark-375.png') })
    await dark.page.goto('/movie-night')
    await expect(dark.page.getByRole('checkbox', { name: 'Mark' })).toBeVisible()
    await dark.page.screenshot({ path: testInfo.outputPath('ae10-start-craig-dark-375.png'), fullPage: true })
  } finally {
    // The night first (its suggestion names the film), then the film's viewings, copy and row,
    // the copy for good: a plain DELETE only moves it to the Trash (migration 013's trigger).
    if (nightId) db.sql(`DELETE FROM movie_night_sessions WHERE id = ${sql(nightId)}`)
    db.sql(`BEGIN; SET LOCAL app.permanent_delete = 'on';
      DELETE FROM movie_night_suggestions WHERE movie_id = ${sql(film.id)};
      DELETE FROM watch_log WHERE movie_id = ${sql(film.id)};
      DELETE FROM collection_items WHERE movie_id = ${sql(film.id)};
      DELETE FROM movies WHERE id = ${sql(film.id)}; COMMIT`)
    expect(db.scalar(`SELECT count(*) FROM movies WHERE id = ${sql(film.id)}`)).toBe('0')
  }
})

// E: a night nobody touched closes two days after it started, and keeps its list.
test('AE10 a night nobody touched for two days closes itself when nights are read', async ({ api, db, signedIn }) => {
  const craig = await api('Craig')
  const craigId = (await craig.get<{ id: string }>('/auth/me')).id
  const night = randomUUID()
  db.sql(`INSERT INTO movie_night_sessions (id,created_by,invite_token,filters,status,created_at,updated_at) VALUES (${sql(night)},${sql(craigId)},${sql(randomUUID())},'{}'::jsonb,'open',now() - interval '3 days',now() - interval '3 days');
    INSERT INTO movie_night_participants (id,session_id,user_id) VALUES (${sql(randomUUID())},${sql(night)},${sql(craigId)});`)
  try {
    await craig.get('/movie-night')
    expect(db.scalar(`SELECT status FROM movie_night_sessions WHERE id = ${sql(night)}`)).toBe('ended')
    expect(db.scalar(`SELECT ended_at_utc = created_at + interval '2 days' FROM movie_night_sessions WHERE id = ${sql(night)}`)).toBe('t')
    const { page } = await signedIn('Craig')
    await page.goto(`/movie-night/${night}`)
    await expect(page.getByText(/this one has ended/)).toBeVisible()
  } finally {
    db.sql(`DELETE FROM movie_night_sessions WHERE id = ${sql(night)}`)
  }
})
