import { filmId } from '../support/films.ts'
import { pushesTo, registerDevice } from '../support/push.ts'
import { runJob } from '../support/cli.ts'
import { expect, test } from '../support/test.ts'
import { world } from '../support/world.ts'

test.describe('price alert from a shop', () => {
  test('a shop price under the limit reaches the Wanted card and the phone; one over it does not', async ({ signedIn, api }) => {
    const craig = await api('Craig')
    await craig.post('/wanted', { tmdbId: 1401, preferredFormat: 'blu_ray', maxPrice: '10.00' }) // Ember Coast
    await craig.post('/wanted', { tmdbId: 1402, preferredFormat: 'blu_ray', maxPrice: '5.00' }) // Salt And Static
    world.setScenario({
      shops: {
        'www.zavvi.com': [
          { match: 'ember coast', title: 'Ember Coast Blu-ray', price: '8.99' },
          { match: 'salt and static', title: 'Salt And Static Blu-ray', price: '12.99' },
        ],
      },
    })
    const phone = await registerDevice(craig, 'craig-phone')

    // "Run now" on the shops page is the same pass the nightly cron makes.
    const run = await craig.post<{ alertsQueued: number; pushesSent: number; succeeded: number }>('/scrapers/daily')
    expect(run.succeeded).toBeGreaterThanOrEqual(2)
    expect(run.pushesSent).toBeGreaterThanOrEqual(1)

    const pushed = pushesTo(phone)
    expect(pushed.map((p) => p.title)).toContain('Ember Coast is £8.99')
    expect(pushed.some((p) => String(p.title).includes('Salt And Static'))).toBe(false)
    expect(pushed.find((p) => String(p.title).includes('Ember Coast'))?.url).toBe('/wanted')

    // Wanted lists each shop's latest price with its day and a link (X11), alert or not.
    const { page } = await signedIn('Craig')
    await page.goto('/wanted')
    const ember = page.getByRole('listitem').filter({ has: page.getByRole('link', { name: 'Ember Coast', exact: true }) })
    await expect(ember.getByRole('list', { name: 'Latest shop prices' }).getByRole('link', { name: /^Zavvi £8\.99/ })).toBeVisible()
    const salt = page.getByRole('listitem').filter({ has: page.getByRole('link', { name: 'Salt And Static', exact: true }) })
    await expect(salt.getByRole('list', { name: 'Latest shop prices' }).getByRole('link', { name: /^Zavvi £12\.99/ })).toBeVisible()
  })
})

test.describe('eBay price alert', () => {
  test('Mark sets an alert on a film; the eBay pass finds a listing at his price and tells his phone', async ({ signedIn, api }) => {
    const mark = await api('Mark')
    const phone = await registerDevice(mark, 'mark-phone')
    const quietEngine = await filmId(mark, 'The Quiet Engine') // 2011, 4K on the shelf

    const { page } = await signedIn('Mark')
    await page.goto(`/movies/${quietEngine}`)
    const panel = page.getByRole('region', { name: 'eBay price alert' })
    await panel.getByRole('combobox', { name: 'Format' }).selectOption({ label: 'Blu-ray' })
    await panel.getByRole('textbox', { name: 'Your price (£)' }).fill('9.00')
    await panel.getByRole('button', { name: 'Alert me' }).click()

    world.setScenario({
      ebay: {
        searches: [
          {
            contains: 'quiet engine',
            listings: [
              { title: 'The Quiet Engine Blu-ray (2011)', price: '7.50', legacyItemId: '810001' },
              { title: 'The Quiet Engine 4K UHD Blu-ray (2011) Steelbook', price: '25.00', legacyItemId: '810002' },
            ],
          },
        ],
      },
    })
    // The cron job's own entry point, as Railway runs it, against the throwaway database.
    const pass = runJob('src.scripts.ebay_watch')
    expect(pass.status, pass.output).toBe(0)
    expect(pass.output).toMatch(/targets checked: \d+, met [1-9]/)

    const pushed = pushesTo(phone)
    expect(pushed.map((p) => p.title)).toEqual(['The Quiet Engine on Blu-ray: £7.50'])
    expect(pushed[0].url).toBe('https://www.ebay.co.uk/itm/810001')

    // The alert screen says what the pass found, and the 4K decoy at £25 is not it.
    await page.goto('/price-alerts')
    const alert = page.getByRole('listitem').filter({ has: page.getByRole('heading', { name: 'Any Blu-ray of The Quiet Engine' }) })
    await expect(alert.getByText('Cheapest UK copy: £7.50, free postage.')).toBeVisible()
    await expect(alert.getByRole('link', { name: 'Open on eBay' })).toHaveAttribute('href', 'https://www.ebay.co.uk/itm/810001')
  })

  test('a single listing can be watched by its address, and an alert can be removed', async ({ signedIn }) => {
    const { page } = await signedIn('Mark')
    await page.goto('/price-alerts')
    await page.getByRole('textbox', { name: 'Listing address' }).fill('https://www.ebay.co.uk/itm/810099')
    await page.getByRole('textbox', { name: 'Your price (£)' }).first().fill('4.00')
    await page.getByRole('button', { name: 'Watch this listing' }).click()
    const mine = page.getByRole('region', { name: 'Your alerts' })
    await expect(mine.getByText('Watching').first()).toBeVisible()
    await expect(mine.getByRole('link', { name: /ebay|THE BRAZEN BULL/i }).first()).toBeVisible()

    const before = await mine.getByRole('button', { name: 'Remove' }).count()
    await mine.getByRole('button', { name: 'Remove' }).first().click()
    await expect(mine.getByRole('button', { name: 'Remove' })).toHaveCount(before - 1)
  })
})
