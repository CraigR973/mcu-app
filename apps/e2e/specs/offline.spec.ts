import type { Page } from '@playwright/test'
import { filmId } from '../support/films.ts'
import { API_ORIGIN } from '../harness/env.ts'
import { expect, test } from '../support/test.ts'

async function workerInControl(page: Page) {
  await page.waitForFunction(() => 'serviceWorker' in navigator && navigator.serviceWorker.ready.then(() => true))
  // The first load installs the worker; the next one is controlled by it.
  await page.reload()
  await page.waitForFunction(() => !!navigator.serviceWorker.controller)
}


async function queueState(page: Page): Promise<string> {
  return page.evaluate(
    () =>
      new Promise<string>((resolve) => {
        const open = indexedDB.open('mcu-offline')
        open.onsuccess = () => {
          const tx = open.result.transaction('writes', 'readonly')
          const all = tx.objectStore('writes').getAll()
          all.onsuccess = () => resolve(JSON.stringify((all.result as { state: string; error?: string }[]).map((e) => [e.state, e.error])))
        }
        open.onerror = () => resolve('idb error')
      }),
  )
}

test.describe('offline, against an API on another origin', () => {
  test('the worker keeps the API\'s answers, and with the API gone a film read online still opens', async ({ signedIn, api, apiProcess }) => {
    const film = await filmId(await api('Craig'), 'Copper Canyon')
    const { page } = await signedIn('Craig', { worker: true })
    await page.goto(`/movies/${film}`)
    await workerInControl(page)
    await expect(page.getByRole('heading', { name: 'Copper Canyon', level: 1 })).toBeVisible()
    // Let each screen finish loading before leaving it: leaving mid-load aborts its lazy chunks,
    // and the app answers a failed chunk by reloading, which Firefox reports as a failed navigation.
    await page.goto('/dashboard')
    await expect(page.getByRole('heading', { name: 'Home', level: 1 })).toBeVisible()
    await page.goto(`/movies/${film}`)
    await expect(page.getByRole('heading', { name: 'Copper Canyon', level: 1 })).toBeVisible()

    // UX48-01: production's API is not the page's origin, and the rule once matched only the
    // page's own, so nothing was ever kept. Every kept answer here is from the API's origin.
    const kept = await page.evaluate(async () => {
      const urls: string[] = []
      for (const name of await caches.keys()) {
        for (const request of await (await caches.open(name)).keys()) urls.push(request.url)
      }
      return urls
    })
    const fromApi = kept.filter((url) => url.startsWith(`${API_ORIGIN}/api/v1/`))
    expect(fromApi.length, JSON.stringify(kept.slice(0, 8))).toBeGreaterThan(0)
    expect(kept.filter((url) => url.includes('/api/v1/') && !url.startsWith(API_ORIGIN))).toEqual([])

    await apiProcess.stop()
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Copper Canyon', level: 1 })).toBeVisible()
  })

  test('a replay whose answer is lost is checked, not sent twice: one copy exists afterwards (CR43-05)', async ({ signedIn, api, db, browserName }) => {
    const craig = await api('Craig')
    const copies = () =>
      db.scalar(
        "SELECT count(*) FROM collection_items ci JOIN movies m ON m.id = ci.movie_id WHERE m.title = 'Paper Lantern' AND ci.deleted_at IS NULL",
      )
    // A film the catalogue already knows, so the add names it by id and a lost answer can be
    // read back. (One added by TMDB id alone has nothing to read back by.)
    const wanted = await craig.post<{ movieId: string }>('/wanted', { tmdbId: 1403 })
    const { context, page } = await signedIn('Craig', { worker: true })
    await page.goto('/collection/add')
    await workerInControl(page)
    // Open the film's own screen once while there is a connection, so the page has its code in
    // hand when the add sends the person there: WebKit under Playwright cannot fetch a lazy chunk
    // offline, which is a limit of its offline switch, not the point of this case.
    await page.goto(`/movies/${wanted.movieId}`)
    await expect(page.getByRole('heading', { name: 'Paper Lantern', level: 1 })).toBeVisible()
    await page.getByRole('link', { name: 'Add a copy' }).click()
    await page.getByRole('tab', { name: 'Search title' }).click()
    await page.getByRole('textbox', { name: 'Search for a film' }).fill('Paper Lantern')
    await page.getByRole('button', { name: 'Search', exact: true }).click()
    await page.getByRole('list', { name: 'Films found' }).getByRole('button', { name: /Paper Lantern/ }).first().click()
    await page.getByRole('combobox', { name: 'Section' }).selectOption({ label: 'Garage' })
    await page.getByRole('textbox', { name: 'Location' }).fill('Garage replay shelf')

    // 1. No connection when "Add" is pressed: the browser never sent it, so it waits as `queued`.
    await context.setOffline(true)
    await page.getByRole('button', { name: 'Add “Paper Lantern”', exact: true }).click()
    const banner = page.getByTestId('offline-banner')
    // Chromium and Firefox know the connection is gone and say so; WebKit under Playwright still
    // thinks it is online, so the same banner says a change is waiting. Either is the banner, and
    // the queue's state is what is asserted.
    await expect(banner).toContainText(/You’re offline|waiting to sync/)
    expect(await queueState(page)).toBe('[["queued",null]]')

    // 2. The connection returns and the replay goes out. It reaches the server and lands, but the
    // answer is lost on the way back (a 503): this is the step CR43-05 found untested.
    await page.route(`${API_ORIGIN}/api/v1/collection`, async (route) => {
      if (route.request().method() !== 'POST') return route.continue()
      const response = await route.fetch()
      return route.fulfill({ response, status: 503, body: 'upstream gone' })
    })
    await context.setOffline(false)
    // Chromium and Firefox announce the connection coming back; WebKit under Playwright does not
    // fire `online`, which is the event the app flushes on. Say it for that browser.
    if (browserName === 'webkit') await page.evaluate(() => window.dispatchEvent(new Event('online')))
    await expect.poll(() => queueState(page)).toBe('[["unconfirmed",null]]')
    expect(copies()).toBe('1')

    // 3. The next sync reads the shelf back instead of sending it again.
    await page.unroute(`${API_ORIGIN}/api/v1/collection`)
    await banner.getByRole('button', { name: 'Sync now' }).click()
    await expect(banner).toHaveCount(0)
    expect(copies()).toBe('1')
    expect(await queueState(page)).toBe('[]')
  })
})
