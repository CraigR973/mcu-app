import { API_ORIGIN } from '../harness/env.ts'
import { filmId } from '../support/films.ts'
import { expect, test } from '../support/test.ts'

for (const width of [1280, 375]) test(`a movie-night response during a pointer press cannot move Add a copy at ${width}px`, async ({ api, signedIn, db }) => {
  const caller = await api('Craig')
  const id = await filmId(caller, 'Copper Canyon')
  const nights = [await caller.post<{ id: string }>('/movie-night', {}), await caller.post<{ id: string }>('/movie-night', {})]
  try {
    const { page } = await signedIn('Craig')
    await page.setViewportSize({ width, height: 844 })
    let release!: () => void
    const held = new Promise<void>(resolve => { release = resolve })
    let requested!: () => void
    const requestSeen = new Promise<void>(resolve => { requested = resolve })
    await page.route(`${API_ORIGIN}/api/v1/movie-night`, async route => {
      const response = await route.fetch()
      requested()
      await held
      await route.fulfill({ response })
    })
    await page.goto(`/movies/${id}`)
    await expect(page.getByRole('heading', { name: 'Copper Canyon', level: 1 })).toBeVisible()
    await requestSeen
    const link = page.getByRole('link', { name: 'Add a copy' })
    await link.scrollIntoViewIfNeeded()
    const layoutBefore = await link.evaluate(element => (element as HTMLElement).offsetTop)
    const before = await link.boundingBox()
    expect(before).not.toBeNull()
    const point = { x: before!.x + before!.width / 2, y: before!.y + before!.height / 2 }
    await page.mouse.move(point.x, point.y)
    await page.mouse.down()
    release()
    await expect(page.getByRole('button', { name: 'Add to movie night', exact: true })).toBeVisible()
    const after = await link.boundingBox()
    console.log('held movie-night pointer geometry', JSON.stringify({ before, after }))
    const layoutAfter = await link.evaluate(element => (element as HTMLElement).offsetTop)
    await page.mouse.up()
    expect(layoutAfter).toBe(layoutBefore)
    await expect(page.getByRole('tab', { name: 'Search title' })).toBeVisible()
  } finally {
    db.sql(`UPDATE movie_night_sessions SET status = 'ended', ended_at_utc = timezone('utc', now()) WHERE id IN (${nights.map(night => `'${night.id}'`).join(',')})`)
  }
})
