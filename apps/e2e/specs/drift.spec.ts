import { API_ORIGIN } from '../harness/env.ts'
import { filmId } from '../support/films.ts'
import { expect, test } from '../support/test.ts'

test.describe('a phone that is out of date with the app (UX48-03)', () => {
  test('an answer with a value this build has never seen says so and offers Reload, not raw text', async ({ signedIn, api }) => {
    const film = await filmId(await api('Craig'), 'Copper Canyon') // owned on DVD
    const { page } = await signedIn('Craig')
    // The API has gained a way of setting a title aside since this page loaded: the film's own answer names
    // one the build cannot read.
    const copiesOfTheFilm = (url: URL) => url.origin === API_ORIGIN && url.pathname === `/api/v1/movies/${film}`
    await page.route(copiesOfTheFilm, async (route) => {
      const response = await route.fetch()
      const body = (await response.text()).replaceAll('"setAsideAs":null', '"setAsideAs":"podcast"')
      return route.fulfill({ response, body })
    })
    await page.goto(`/movies/${film}`)

    // The banner at the top (with Reload), and the screen's own panel saying the same in words.
    const notice = page.getByRole('alert').filter({ has: page.getByRole('button', { name: 'Reload' }) })
    await expect(page.getByText('Could not open this film')).toBeVisible()
    await expect(notice).toBeVisible()
    await expect(notice).toContainText('This screen needs the newest version')
    // Never the parser's own words or a page of JSON.
    await expect(page.getByText(/invalid_enum_value|ZodError|Expected/)).toHaveCount(0)

    // Reload fetches what the API now sends, and the screen reads again.
    await page.unroute(copiesOfTheFilm)
    await notice.getByRole('button', { name: 'Reload' }).click()
    await expect(page.getByRole('heading', { name: 'Copper Canyon', level: 1 })).toBeVisible()
    await expect(page.getByText('This screen needs the newest version')).toHaveCount(0)
  })

  test('a lazy chunk a deploy removed reloads the page once, then offers Reload, and recovers once it is back', async ({ signedIn }) => {
    const { page } = await signedIn('Craig')
    await page.goto('/you')
    // Vercel answers an unknown /assets/*.js with index.html at 200 (STATUS, 10 Sep): the
    // script loads, and is not JavaScript.
    const indexHtml = await (await page.request.get('/')).text()
    await page.route(/\/assets\/WantedPage-[^/]+\.js$/, (route) =>
      route.fulfill({ status: 200, contentType: 'text/html', body: indexHtml }),
    )

    let loads = 0
    page.on('load', () => (loads += 1))
    await page.getByRole('main').getByRole('link', { name: 'Wanted' }).click()

    const failed = page.getByText('Something went wrong')
    await expect(failed).toBeVisible()
    await expect(page.getByText('This screen needs the newest version').first()).toBeVisible()
    // One reload, tried and failed the same way: never a loop.
    const afterFirst = loads
    await page.waitForTimeout(2500)
    expect(loads).toBe(afterFirst)
    expect(afterFirst).toBeLessThanOrEqual(1)

    await page.unroute(/\/assets\/WantedPage-[^/]+\.js$/)
    await page.getByRole('button', { name: 'Reload' }).first().click()
    await expect(page.getByRole('heading', { name: 'Wanted', level: 1 })).toBeVisible()
  })
})
