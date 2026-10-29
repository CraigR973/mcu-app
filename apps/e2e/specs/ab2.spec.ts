import { expect, PINS, test } from '../support/test.ts'

type Stats = { totalMovies: number; watchedMovies: number; ownedWatchedMovies: number }
type Copy = { id: string; movieId: string }
const counts = ({ totalMovies, watchedMovies, ownedWatchedMovies }: Stats): Stats => ({ totalMovies, watchedMovies, ownedWatchedMovies })
const coverage = (stats: Stats) => `${stats.ownedWatchedMovies.toLocaleString('en-GB')} / ${stats.totalMovies.toLocaleString('en-GB')}`

for (const person of ['Craig', 'Mark'] as const) {
  test(`AB2 refreshes ${person}'s cached coverage after a watch and preserves diary through copy departure`, async ({ signedIn, api }) => {
    const client = await api(person)
    const owner = await api('Craig')
    const copy = await owner.post<Copy>('/collection', { tmdbId: 1701, formats: ['download'], hasPlaybackIssues: false })
    const watches: string[] = []
    try {
      const before = await client.get<Stats>('/collection/stats')
      const { page } = await signedIn(person)
      await page.setViewportSize({ width: 375, height: 844 })
      await page.goto('/dashboard')
      const numbers = page.getByRole('list', { name: 'The collection in numbers' })
      const watched = numbers.locator('li').filter({ hasText: "You've watched" })
      await expect(watched).toContainText(coverage(before))
      // Use client-side navigation, retaining the Home query's five-minute cache.
      await page.getByRole('navigation', { name: 'Primary mobile navigation' }).getByRole('button', { name: 'Search the archive' }).click()
      const search = page.getByRole('dialog', { name: 'Search the archive' }).getByRole('combobox', { name: 'Search films' })
      const film = await client.get<{ title: string }>(`/movies/${copy.movieId}`)
      await search.fill(film.title)
      await page.getByRole('option', { name: new RegExp(film.title) }).first().click()
      await expect(page.getByRole('button', { name: 'Mark watched', exact: true })).toBeEnabled()
      await page.getByRole('button', { name: 'Mark watched', exact: true }).click()
      await expect(page.getByRole('button', { name: 'Log a rewatch', exact: true })).toBeEnabled()
      const log = await client.get<{ items: { id: string }[] }>(`/watch-log?movieId=${copy.movieId}`)
      watches.push(...log.items.map(item => item.id))
      const afterWatch = await client.get<Stats>('/collection/stats')
      expect(afterWatch.ownedWatchedMovies).toBe(before.ownedWatchedMovies + 1)
      expect(afterWatch.watchedMovies).toBe(before.watchedMovies + 1)
      await page.getByRole('navigation', { name: 'Primary mobile navigation' }).getByRole('link', { name: 'Home', exact: true }).click()
      await expect(watched).toContainText(coverage(afterWatch))
      const rewatch = await client.post<{ id: string }>('/watch-log', { movieId: copy.movieId, isRewatch: true })
      watches.push(rewatch.id)
      expect(await client.get<Stats>('/collection/stats')).toMatchObject(counts(afterWatch))
      await owner.put(`/collection/${copy.id}/listing`, { status: 'listed_for_sale' })
      expect(await client.get<Stats>('/collection/stats')).toMatchObject(counts(afterWatch))
      await owner.put(`/collection/${copy.id}/listing`, { status: 'sold' })
      const departed = await client.get<Stats>('/collection/stats')
      expect(departed.ownedWatchedMovies).toBe(before.ownedWatchedMovies)
      expect(departed.totalMovies).toBe(before.totalMovies - 1)
      expect(departed.watchedMovies).toBe(afterWatch.watchedMovies)
      await page.reload()
      await expect(watched).toContainText(coverage(departed))
      await owner.put(`/collection/${copy.id}/listing`, { status: 'in_collection' })
      expect(await client.get<Stats>('/collection/stats')).toMatchObject(counts(afterWatch))
      await client.delete(`/watch-log/${watches.pop()!}`)
      expect((await client.get<Stats>('/collection/stats')).ownedWatchedMovies).toBe(afterWatch.ownedWatchedMovies)
      await client.delete(`/watch-log/${watches.pop()!}`)
      expect(await client.get<Stats>('/collection/stats')).toMatchObject(counts(before))
    } finally {
      for (const id of watches) await client.delete(`/watch-log/${id}`)
      await owner.delete(`/collection/${copy.id}`)
    }
  })
}

test('AB2 shows unavailable for an older stats answer, never its diary count', async ({ signedIn }) => {
  const { page } = await signedIn('Craig')
  await page.route('**/api/v1/collection/stats', async route => {
    const response = await route.fetch()
    const body = await response.json() as Omit<Stats, 'ownedWatchedMovies'> & { ownedWatchedMovies?: number }
    delete body.ownedWatchedMovies
    await route.fulfill({ response, json: body })
  })
  await page.goto('/dashboard')
  const card = page.getByRole('list', { name: 'The collection in numbers' }).locator('li').filter({ hasText: "You've watched" })
  await expect(card).toContainText('Unavailable')
  await expect(card).toContainText('Watched coverage is unavailable in this saved response.')
  await expect(card).not.toContainText(' / ')
})

test('AB2 isolates the personal numerator when two people use the same browser', async ({ signedIn, api }) => {
  const craig = await api('Craig')
  const copy = await craig.post<Copy>('/collection', { tmdbId: 1701, formats: ['download'], hasPlaybackIssues: false })
  const watch = await craig.post<{ id: string }>('/watch-log', { movieId: copy.movieId })
  try {
    const mine = await craig.get<Stats>('/collection/stats')
    const theirs = await (await api('Mark')).get<Stats>('/collection/stats')
    expect(mine.ownedWatchedMovies).not.toBe(theirs.ownedWatchedMovies)
    const { page } = await signedIn('Craig')
    await page.setViewportSize({ width: 375, height: 844 })
    await page.goto('/dashboard')
    const card = page.getByRole('list', { name: 'The collection in numbers' }).locator('li').filter({ hasText: "You've watched" })
    await expect(card).toContainText(coverage(mine))
    await page.getByRole('link', { name: 'You: every other page, and your account' }).click()
    await page.getByRole('main').getByRole('button', { name: 'Sign out', exact: true }).click()
    await page.getByLabel('Name').fill('Mark')
    await page.getByLabel('PIN', { exact: true }).fill(PINS.Mark)
    await page.getByRole('button', { name: 'Enter the archive', exact: true }).click()
    await expect(page.getByRole('region', { name: 'Signed in as' })).toContainText('Mark')
    await page.getByRole('navigation', { name: 'Primary mobile navigation' }).getByRole('link', { name: 'Home', exact: true }).click()
    await expect(card).toContainText(coverage(theirs))
  } finally {
    await craig.delete(`/watch-log/${watch.id}`)
    await craig.delete(`/collection/${copy.id}`)
  }
})

test('AB2 renders four-digit coverage and a stored estimate at 375 px in both themes', async ({ signedIn }, testInfo) => {
  const { page, context } = await signedIn('Craig')
  // Deliberately large fixture figures, not pinned expectations about the live catalogue.
  await page.route('**/api/v1/collection/stats', async route => {
    const response = await route.fetch()
    await route.fulfill({ response, json: { ...await response.json(), totalMovies: 5678, ownedWatchedMovies: 1234 } })
  })
  await page.route('**/api/v1/collection/value', async route => {
    const response = await route.fetch()
    await route.fulfill({ response, json: { ...await response.json(), total: '12345.67', discs: 5678, pricedDiscs: 1234, salesBackedDiscs: 12 } })
  })
  for (const theme of ['dark', 'light']) {
    await context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
    await page.setViewportSize({ width: 375, height: 844 })
    await page.goto('/dashboard')
    const section = page.getByRole('region', { name: 'The collection', exact: true })
    await expect(section.getByText('1,234 / 5,678', { exact: true })).toBeVisible()
    await expect(section.getByText('≈ £12,346', { exact: true })).toBeVisible()
    await expect(section.getByText('12 based on observed sales', { exact: true })).toBeVisible()
    expect(await section.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true)
    await page.setViewportSize({ width: 375, height: 1600 })
    await section.screenshot({ path: testInfo.outputPath(`ab2-summary-${theme}-375.png`) })
    await page.setViewportSize({ width: 375, height: 844 })
    await section.getByText('How this estimate works', { exact: true }).click()
    await expect(section.getByText(/At least three observed sales/)).toBeVisible()
    await expect(section.getByText(/a Best Offer may have closed below its advertised price/)).toBeVisible()
  }
})
