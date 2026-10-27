import type { Page, Request, Response, Route } from '@playwright/test'
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

  test('a replay whose answer is lost is checked, not sent twice, whether the add names the film by its id or by TMDB id: one copy each afterwards (CR43-05)', async ({ signedIn, api, db, browserName }) => {
    // Visible in the report, with its reason. The replay's logic is also held by vitest cases
    // (`sync.test.ts`) and runs here on Chromium and Firefox.
    test.skip(
      browserName === 'webkit',
      "Playwright's WebKit does not let a case intercept the replayed POST (the page saw the server's own 201 twice), so the answer cannot be lost there",
    )
    const craig = await api('Craig')
    const copiesOf = (tmdbId: number) =>
      db.scalar(
        `SELECT count(*) FROM collection_items ci JOIN movies m ON m.id = ci.movie_id WHERE m.tmdb_id = ${tmdbId} AND ci.deleted_at IS NULL`,
      )
    // A film the catalogue already knows, so the add names it by its film id.
    const wanted = await craig.post<{ movieId: string }>('/wanted', { tmdbId: 1403 })
    const { context, page } = await signedIn('Craig', { worker: true })
    await page.goto('/collection/add')
    await workerInControl(page)
    // Worker control precedes React's lazy screen: leaving before its chunks finish
    // aborts their imports and the app's recovery reload cancels the next navigation.
    await expect(page.getByRole('main').getByRole('heading', { name: 'Add a disc', level: 1 })).toBeVisible()
    // Open the film's own screen once while there is a connection, so the page has its code in
    // hand when the add sends the person there: WebKit under Playwright cannot fetch a lazy chunk
    // offline, which is a limit of its offline switch, not the point of this case.
    await page.goto(`/movies/${wanted.movieId}`)
    await expect(page.getByRole('heading', { name: 'Paper Lantern', level: 1 })).toBeVisible()
    const banner = page.getByTestId('offline-banner')

    /** Choose the film from a TMDB search on the add form and fill in where the disc lives. */
    async function chooseFilm(title: string, location: string) {
      await page.getByRole('tab', { name: 'Search title' }).click()
      await page.getByRole('textbox', { name: 'Search for a film' }).fill(title)
      await page.getByRole('button', { name: 'Search', exact: true }).click()
      await page.getByRole('list', { name: 'Films found' }).getByRole('button', { name: new RegExp(title) }).first().click()
      await page.getByRole('combobox', { name: 'Section' }).selectOption({ label: 'Garage' })
      await page.getByRole('textbox', { name: 'Location' }).fill(location)
    }

    /**
     * 1. No connection when "Add" is pressed: the browser never sent it, so it waits as `queued`.
     * 2. The connection returns and the replay goes out. It reaches the server and lands, but the
     *    answer is lost on the way back (the connection is reset): the step CR43-05 found untested.
     * 3. The next sync reads the shelf back instead of sending it again.
     */
    async function addWithItsAnswerLost(title: string, tmdbId: number) {
      await context.setOffline(true)
      await page.getByRole('button', { name: `Add “${title}”`, exact: true }).click()
      // Chromium and Firefox know the connection is gone and say so; WebKit under Playwright still
      // thinks it is online, so the same banner says a change is waiting. Either is the banner, and
      // the queue's state is what is asserted.
      await expect(banner).toContainText(/You’re offline|waiting to sync/)
      expect(await queueState(page)).toBe('[["queued",null]]')

      const seen: string[] = []
      const answers = (r: Response) =>
        r.url().endsWith('/api/v1/collection') && seen.push(`${r.request().method()} ${r.status()}`)
      const failures = (r: Request) =>
        r.url().endsWith('/api/v1/collection') && seen.push(`failed ${r.failure()?.errorText}`)
      page.on('response', answers)
      page.on('requestfailed', failures)
      const loseTheAnswer = async (route: Route) => {
        if (route.request().method() !== 'POST') return route.continue()
        await route.fetch() // the server has it
        return route.abort('connectionreset') // and the answer never reaches the page
      }
      await page.route(`${API_ORIGIN}/api/v1/collection`, loseTheAnswer)
      await context.setOffline(false)
      // Chromium and Firefox announce the connection coming back; WebKit under Playwright does not
      // fire `online`, which is the event the app flushes on. Say it for that browser.
      if (browserName === 'webkit') await page.evaluate(() => window.dispatchEvent(new Event('online')))
      try {
        await expect.poll(() => queueState(page)).toBe('[["unconfirmed",null]]')
      } catch (failure) {
        throw new Error(`the page saw these answers to its add: ${seen.join(', ') || 'none'}\n${String(failure)}`)
      } finally {
        page.off('response', answers)
        page.off('requestfailed', failures)
      }
      expect(copiesOf(tmdbId)).toBe('1')

      await page.unroute(`${API_ORIGIN}/api/v1/collection`, loseTheAnswer)
      await banner.getByRole('button', { name: 'Sync now' }).click()
      await expect(banner).toHaveCount(0)
      expect(copiesOf(tmdbId)).toBe('1')
      expect(await queueState(page)).toBe('[]')
    }

    // A film the catalogue knows: the lost add is read back by its film id.
    await page.getByRole('link', { name: 'Add a copy' }).click()
    await chooseFilm('Paper Lantern', 'Garage replay shelf')
    await addWithItsAnswerLost('Paper Lantern', 1403)

    // A film it has never seen (Batch Z1, DECISIONS.md #287): the add names it by its TMDB id
    // alone, so there is no film id to read it back by. It used to stay "never heard back" for
    // good; it is read back through the duplicate check instead.
    expect(copiesOf(1404)).toBe('0')
    await page.goto('/collection/add')
    await chooseFilm('Paper Kite', 'Garage replay shelf')
    await addWithItsAnswerLost('Paper Kite', 1404)
  })
})
