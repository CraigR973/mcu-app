import type { Route } from '@playwright/test'
import { runJob } from '../support/cli.ts'
import { pushesTo, registerDevice } from '../support/push.ts'
import { filmId } from '../support/films.ts'
import { expect, test } from '../support/test.ts'

test.describe('movie night', () => {
  test('Craig sends a night, the push opens it for Mark, they pick the same film and both see the match', async ({ signedIn, api }) => {
    const craigPhone = await registerDevice(await api('Craig'), 'craig-phone')
    const markPhone = await registerDevice(await api('Mark'), 'mark-phone')

    const craig = await signedIn('Craig')
    await craig.page.goto('/movie-night')
    await craig.page.getByLabel('Planned date and time (optional)').fill('2026-11-01T20:30')
    await craig.page.getByRole('button', { name: 'Start movie night' }).click()
    await expect(craig.page).toHaveURL(/\/movie-night\/[0-9a-f-]{36}$/)
    const nightUrl = new URL(craig.page.url()).pathname
    await craig.page.getByRole('button', { name: 'Send to Mark' }).click()

    // What reached Mark's phone says which night to open.
    await expect.poll(() => pushesTo(markPhone).length, { message: 'a push to Mark' }).toBeGreaterThan(0)
    const [invite] = pushesTo(markPhone)
    expect(invite.title).toBe('Craig started a movie night')
    expect(invite.url).toBe(nightUrl)
    expect(invite.body).toContain('Planned for 1 Nov 2026 at 20:30 GMT')

    // Both look at the same shortlist; Craig picks the first film on it.
    const shortlist = craig.page.getByRole('region', { name: /Stuck for ideas/ })
    const firstAdd = shortlist.getByRole('button', { name: /^Add / }).first()
    const film = (await firstAdd.innerText()).replace(/\s+/g, ' ').replace(/^Add\s*/, '').trim()
    await firstAdd.click()
    await expect(shortlist.getByText("You've added 1")).toBeVisible()

    // Mark opens the night the way the notification does: by its address.
    const mark = await signedIn('Mark')
    await mark.page.goto(invite.url as string)
    await expect(mark.page.getByRole('heading', { name: 'Movie night', level: 1 })).toBeVisible()
    await mark.page.getByRole('button', { name: `Add ${film}` }).click()
    await expect(mark.page.getByText("It's a match")).toBeVisible()

    // Craig is told by push.
    await expect.poll(() => pushesTo(craigPhone).map((p) => p.title).join('|')).toContain('match')

    // The match is stored on the night: a fresh page, with no live message, still shows it, for
    // either person, and the night names the film.
    await mark.page.reload()
    await expect(mark.page.getByText("It's a match")).toBeVisible()
    await expect(mark.page.getByText(film).first()).toBeVisible()
    await craig.page.reload()
    await expect(craig.page.getByText("It's a match")).toBeVisible()
    await expect(craig.page.getByText(film).first()).toBeVisible()
  })

  test("a page left open on the night is told of the match as it happens", async ({ signedIn, api, browserName }) => {
    // Visible in the report, with its reason. Under Playwright's WebKit the open page did not show
    // the match that Chromium and Firefox show within a second, while a second listener on the
    // same stream received the night's events. Whether Safari does the same is for a real iPhone
    // (OWNER-ACTIONS 16b); the push and the stored match, held on all three browsers by the case
    // above, are how a person is told there. DECISIONS.md #285.
    test.skip(browserName === 'webkit', "Playwright's WebKit does not show a live match on an open page; unproven for Safari")
    await registerDevice(await api('Craig'), 'craig-phone')
    await registerDevice(await api('Mark'), 'mark-phone')

    const craig = await signedIn('Craig')
    await craig.page.goto('/movie-night')
    await craig.page.getByRole('button', { name: 'Start movie night' }).click()
    await expect(craig.page).toHaveURL(/\/movie-night\/[0-9a-f-]{36}$/)
    const nightUrl = new URL(craig.page.url()).pathname
    await craig.page.getByRole('button', { name: 'Send to Mark' }).click()
    const shortlist = craig.page.getByRole('region', { name: /Stuck for ideas/ })
    const firstAdd = shortlist.getByRole('button', { name: /^Add / }).first()
    const film = (await firstAdd.innerText()).replace(/\s+/g, ' ').replace(/^Add\s*/, '').trim()
    await firstAdd.click()
    await expect(shortlist.getByText("You've added 1")).toBeVisible()

    const mark = await signedIn('Mark')
    await mark.page.goto(nightUrl)
    await mark.page.getByRole('button', { name: `Add ${film}` }).click()
    await expect(mark.page.getByText("It's a match")).toBeVisible()

    // Craig has not touched his page: the match arrives over the live stream.
    await expect(craig.page.getByText("It's a match")).toBeVisible()
  })
})


test('a film page adds a random pick to Suggested without losing its vote', async ({ signedIn }, testInfo) => {
  const craig = await signedIn('Craig')
  await craig.page.goto('/movie-night')
  await craig.page.getByRole('button', { name: 'Start movie night' }).click()
  await craig.page.setViewportSize({ width: 375, height: 812 })
  const random = craig.page.getByRole('region', { name: /Stuck for ideas/ })
  const row = random.getByRole('listitem').first()
  const add = row.getByRole('button', { name: /^Add / })
  const title = (await add.innerText()).replace(/^Add\s*/, '').trim()
  await add.click()
  await row.getByRole('button', { expanded: false }).click()
  await row.getByRole('link', { name: 'Open its page' }).click()
  await craig.page.getByRole('button', { name: 'Add to movie night' }).click()
  const suggested = craig.page.getByRole('region', { name: /^Suggested/ })
  await expect(suggested.getByRole('button', { name: `Added ${title}` })).toBeVisible()
  await expect(suggested.getByText(/Suggested by Craig/)).toBeVisible()
  await expect(random.getByRole('button', { name: `Added ${title}` })).toHaveCount(0)
  const headings = craig.page.getByRole('heading', { level: 2 })
  await expect(headings.nth(0)).toHaveText('Suggest a film')
  await expect(headings.nth(1)).toContainText('Suggested')
  await expect(headings.nth(2)).toContainText('Stuck for ideas? A random shortlist')
  await craig.page.screenshot({ path: testInfo.outputPath('aa4-night-375.png'), fullPage: false })
})

test('a poster failure cannot move the movie-night action during a click', async ({ signedIn, api }) => {
  const craig = await signedIn('Craig')
  await craig.page.setViewportSize({ width: 375, height: 812 })
  await craig.page.goto('/movie-night')
  await craig.page.getByRole('button', { name: 'Start movie night' }).click()
  await expect(craig.page).toHaveURL(/\/movie-night\/[0-9a-f-]{36}$/)
  const nightUrl = new URL(craig.page.url()).pathname
  const title = 'Filler Feature 031'
  const id = await filmId(await api('Craig'), title)
  let failPoster!: () => void
  let loadFallback!: () => void
  let requestedPoster!: () => void
  const posterRequested = new Promise<void>((resolve) => { requestedPoster = resolve })
  const posterFailure = new Promise<void>((resolve) => { failPoster = resolve })
  const fallbackReady = new Promise<void>((resolve) => { loadFallback = resolve })
  // Only the film page's poster and fallback are held. The night page's own fallbacks, still
  // loading when the case leaves it, go through: the harness waits for them before it navigates
  // (#367), and a hold on them would never let it.
  const onFilmPage = (route: Route) => new URL(route.request().frame().url()).pathname === `/movies/${id}`
  await craig.page.route('https://image.tmdb.org/t/p/w342/**', async (route) => {
    if (!onFilmPage(route)) return route.continue()
    requestedPoster()
    await posterFailure
    await route.fulfill({ status: 404, contentType: 'text/html', body: 'Poster unavailable' })
  })
  await craig.page.route('**/placeholder-poster.svg', async (route) => {
    if (!onFilmPage(route)) return route.continue()
    await fallbackReady
    await route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 300"></svg>' })
  })
  try {
    await craig.page.goto(`/movies/${id}`)
    await posterRequested
    const poster = craig.page.getByRole('img', { name: `${title} poster` })
    const add = craig.page.getByRole('button', { name: 'Add to movie night' })
    await expect(add).toBeVisible()
    const before = await poster.boundingBox()
    const actionBefore = await add.boundingBox()
    expect(before).not.toBeNull()
    expect(actionBefore).not.toBeNull()
    await craig.page.mouse.move(actionBefore!.x + actionBefore!.width / 2, actionBefore!.y + actionBefore!.height / 2)
    // Layout position excludes the button's intentional animated 1px press transform.
    const actionLayoutBefore = await add.evaluate((element) => {
      if (!(element instanceof HTMLButtonElement)) throw new Error('Movie-night action is not a button')
      return element.offsetTop
    })
    await craig.page.mouse.down()
    failPoster()
    await expect(poster).toHaveAttribute('src', '/placeholder-poster.svg')
    // Observe the failed-image interval, before the local fallback finishes loading.
    await craig.page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))))
    const failed = await poster.boundingBox()
    const actionLayoutFailed = await add.evaluate((element) => {
      if (!(element instanceof HTMLButtonElement)) throw new Error('Movie-night action is not a button')
      return element.offsetTop
    })
    expect(failed?.height).toBeCloseTo(before!.height, 0)
    expect(actionLayoutFailed).toBe(actionLayoutBefore)
    await craig.page.mouse.up()
    await expect(craig.page).toHaveURL(nightUrl)
  } finally {
    failPoster()
    loadFallback()
  }
})


test('AA5: night details use personal history, shelf locations and the nightly IMDb file', async ({ api, db, signedIn }, testInfo) => {
  test.setTimeout(120_000) // Includes the real nightly command, with every provider faked.
  const craigApi = await api('Craig')
  await craigApi.post('/collection', { tmdbId: 1501, formats: ['blu_ray'], section: 'Front', shelf: '2nd', hasPlaybackIssues: false })
  const movieId = db.scalar('SELECT id FROM movies WHERE tmdb_id = 1501')
  await craigApi.post('/watch-log', { movieId, watchedAt: '2026-10-20', personalRating: 4.5 })
  const night = await craigApi.post<{ id: string }>('/movie-night', {})
  await craigApi.post(`/movie-night/${night.id}/send`, {})
  const picked = await craigApi.post<{ items: { suggestionId: string; movieId: string | null; tmdbId: number | null }[] }>(`/movie-night/${night.id}/suggestions`, { movieId })
  const shelf = picked.items.find((item) => item.movieId === movieId)
  expect(shelf).toBeTruthy()
  const extended = await craigApi.post<typeof picked>(`/movie-night/${night.id}/suggestions`, { tmdbId: 1201, title: 'Rooftop Opera', year: 2014 })
  const outside = extended.items.find((item) => item.tmdbId === 1201)
  expect(outside).toBeTruthy()
  const run = runJob('src.scripts.spec_backfill')
  expect(run.status, run.output).toBe(0)
  expect(run.output).toContain('IMDb ratings:')
  const craig = await signedIn('Craig')
  await craig.page.setViewportSize({ width: 375, height: 812 })
  await craig.page.goto(`/movie-night/${night.id}`)
  await craig.page.getByRole('button', { name: /Velvet Observatory 2018/, expanded: false }).click()
  const details = craig.page.locator(`#film-details-${shelf!.suggestionId}`)
  await expect(details.getByRole('list', { name: 'Watch history and personal ratings' })).toContainText('Craig: last watched 20 Oct 2026 · 4.5/5')
  await expect(details.getByRole('list', { name: 'Watch history and personal ratings' })).toContainText('Mark: no watch logged · not rated')
  await expect(details.getByText('Our copies')).toBeVisible()
  await expect(details).toContainText('8.2/10 · 1234 votes')
  await expect(details.getByRole('link', { name: 'Letterboxd' })).toHaveAttribute('href', 'https://letterboxd.com/imdb/tt0001501/')
  await details.getByRole('link', { name: 'Letterboxd' }).scrollIntoViewIfNeeded()
  await craig.page.screenshot({ path: testInfo.outputPath('aa5-details-375.png') })
  await craig.page.getByRole('button', { name: /Rooftop Opera 2014/, expanded: false }).click()
  const external = craig.page.locator(`#film-details-${outside!.suggestionId}`)
  await expect(external).toContainText('1h 52m')
  await expect(external).toContainText('Fake Stream')
  await expect(external).toContainText('8.2/10 · 1234 votes')
  await expect(external.getByRole('link', { name: 'JustWatch via TMDB' })).toHaveAttribute('href', /themoviedb\.org/)
  expect(db.scalar('SELECT count(*) FROM movies WHERE tmdb_id = 1201')).toBe('0')
})

test('Home deals unwatched films without repeats and choosing does not log a watch', async ({ signedIn, api, db }, testInfo) => {
  const user = await signedIn('Craig')
  await user.page.setViewportSize({ width: 375, height: 812 })
  await user.page.goto('/dashboard')
  // AC2 (#337): Feeling lucky is inside Home's featured film, and opening the film is the choice.
  const lucky = user.page.getByRole('group', { name: 'Feeling lucky' })
  const featured = user.page.locator('section').filter({ has: lucky })
  await lucky.getByRole('checkbox').check()
  const before = db.scalar('SELECT count(*) FROM watch_log')
  const suggestionsBefore = db.scalar('SELECT count(*) FROM movie_night_suggestions')
  const dealt: string[] = []
  for (let i = 0; i < 3; i += 1) {
    const response = user.page.waitForResponse((r) => r.url().endsWith('/api/v1/feeling-lucky') && r.request().method() === 'POST')
    await lucky.getByRole('button', { name: /^Deal (a film|another)$/ }).click()
    const answer = await response
    expect(answer.status()).toBe(200)
    const body = await answer.json() as { film: { id: string; title: string; watched: boolean } }
    expect(body.film.watched).toBe(false)
    expect(dealt).not.toContain(body.film.id)
    dealt.push(body.film.id)
    await expect(featured.getByRole('heading', { name: body.film.title })).toBeVisible()
  }
  await featured.scrollIntoViewIfNeeded()
  await user.page.screenshot({ path: testInfo.outputPath('aa6-home-375.png') })
  await expect(featured.getByRole('link', { name: 'Open the film' })).toHaveAttribute('href', `/movies/${dealt[2]}`)
  expect(db.scalar('SELECT count(*) FROM watch_log')).toBe(before)
  expect(db.scalar('SELECT count(*) FROM movie_night_suggestions')).toBe(suggestionsBefore)
  // Dealing on Home has not created a movie-night suggestion.
  const caller = await api('Craig')
  const allSeen = await caller.post<{ film: unknown }>('/feeling-lucky', { excludedIds: dealt, unwatchedOnly: true })
  expect(allSeen.film).toBeTruthy() // The remaining Archive is still available.
})

test('a night deals within its filters and choosing promotes its seed without losing a vote', async ({ signedIn, api, db }, testInfo) => {
  const caller = await api('Craig')
  await caller.post('/collection', { tmdbId: 1601, formats: ['blu_ray'], section: 'Front', shelf: '2nd', hasPlaybackIssues: false })
  const movieId = db.scalar('SELECT id FROM movies WHERE tmdb_id = 1601')
  const night = await caller.post<{ id: string }>('/movie-night', { filters: { decadeFrom: 1930, decadeTo: 1939 } })
  await caller.post(`/movie-night/${night.id}/send`, {})
  const list = await caller.get<{ items: { movieId: string | null; suggestionId: string }[] }>(`/movie-night/${night.id}/candidates`)
  const seed = list.items.find((film) => film.movieId === movieId)
  expect(seed).toBeTruthy()
  await caller.post(`/movie-night/${night.id}/votes`, { suggestionId: seed!.suggestionId, liked: true })
  const user = await signedIn('Craig')
  await user.page.setViewportSize({ width: 375, height: 812 })
  await user.page.goto(`/movie-night/${night.id}`)
  const lucky = user.page.getByRole('group', { name: 'Feeling lucky' })
  await lucky.getByRole('button', { name: 'Deal a film' }).click()
  await expect(lucky.getByRole('heading', { name: 'The Copper Lantern' })).toBeVisible()
  await lucky.scrollIntoViewIfNeeded()
  await user.page.screenshot({ path: testInfo.outputPath('aa6-night-375.png') })
  await lucky.getByRole('button', { name: 'Choose this film' }).click()
  await expect(lucky.getByText(/Added “The Copper Lantern” to tonight’s suggestions/)).toBeVisible()
  const suggested = user.page.getByRole('region', { name: /^Suggested/ })
  await expect(suggested.getByRole('button', { name: 'Added The Copper Lantern' })).toBeVisible()
  const after = await caller.get<{ items: { movieId: string | null; suggestionId: string; suggestedBy: string | null; myVote: boolean | null }[] }>(`/movie-night/${night.id}/candidates`)
  const chosen = after.items.filter((film) => film.movieId === movieId)
  expect(chosen).toHaveLength(1)
  expect(chosen[0]?.suggestionId).toBe(seed!.suggestionId)
  expect(chosen[0]?.myVote).toBe(true)
  expect(chosen[0]?.suggestedBy).toBe('Craig')
  await lucky.getByRole('button', { name: 'Start again' }).click()
  await lucky.getByRole('button', { name: 'Deal a film' }).click()
  await expect(lucky.getByText(/No more films for this run/)).toBeVisible()
})
