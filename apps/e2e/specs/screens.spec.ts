import { WEB_ORIGIN } from '../harness/env.ts'
import { filmId } from '../support/films.ts'
import { probe } from '../support/probe.ts'
import { expect, test } from '../support/test.ts'

// A 1×1 PNG, enough for the photo pipeline to resize and store.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
)

test.describe('screens that had never been used', () => {
  test('box sets: make one, put an owned disc in it, and see how much of the set is on the shelf', async ({ signedIn }) => {
    const { page } = await signedIn('Craig')
    await page.goto('/box-sets')
    await page.getByRole('button', { name: 'New box set' }).click()
    await page.getByRole('textbox', { name: 'Box set name' }).fill('Westerns Box')
    await page.getByRole('textbox', { name: 'Publisher' }).fill('Indicator')
    await page.getByRole('textbox', { name: 'Expected count' }).fill('2')
    await page.getByRole('button', { name: 'Create', exact: true }).click()
    await page.getByRole('link', { name: /^Westerns Box/ }).click()
    await expect(page.getByText('Indicator · 0 of 2')).toBeVisible()

    await page.getByRole('button', { name: 'Add a disc' }).click()
    await page.getByRole('textbox', { name: 'Find a film' }).fill('Copper Canyon')
    await page.getByRole('button', { name: 'Copper Canyon (1972)' }).click()
    await page.getByRole('button', { name: 'DVD · Back 1st shelf' }).click()
    await expect(page.getByText('Indicator · 1 of 2')).toBeVisible()
    await expect(page.getByRole('main').getByText('Copper Canyon').first()).toBeVisible()
  })

  test('smart collections: save a question, see its films, and keep it private to the person who asked', async ({ signedIn }) => {
    const craig = await signedIn('Craig')
    await craig.page.goto('/collections')
    await craig.page.getByRole('button', { name: 'New collection' }).click()
    await craig.page.getByRole('textbox', { name: 'Collection name' }).fill('Garage discs')
    await craig.page.getByRole('combobox', { name: 'Filter by section' }).selectOption({ label: 'Garage (1)' })
    await craig.page.getByRole('button', { name: 'Create collection' }).click()
    await craig.page.getByRole('main').getByRole('link', { name: 'Garage discs' }).click()
    await expect(craig.page.getByRole('heading', { name: 'Garage discs', level: 1 })).toBeVisible()
    await expect(craig.page.getByRole('link', { name: /Harbour Lights/ })).toBeVisible()
    // Mark's list has none of Craig's.
    const mark = await signedIn('Mark')
    await mark.page.goto('/collections')
    await expect(mark.page.getByText('No collections yet')).toBeVisible()
    await expect(mark.page.getByRole('link', { name: 'Garage discs' })).toHaveCount(0)
  })

  test('photos: Craig adds one to a disc and it shows; Mark sees it but is offered no way to add', async ({ signedIn, api }) => {
    const film = await filmId(await api('Craig'), 'The Quiet Engine')
    const craig = await signedIn('Craig')
    await craig.page.goto(`/movies/${film}`)
    await craig.page.locator('input[type="file"]').first().setInputFiles({ name: 'disc.png', mimeType: 'image/png', buffer: PNG })
    await expect(craig.page.getByRole('button', { name: 'Open disc photo' })).toBeVisible()
    await expect(craig.page.getByRole('button', { name: 'Delete photo' })).toBeVisible()

    // Mark sees the photo and is offered no way to add or delete one.
    const mark = await signedIn('Mark')
    await mark.page.goto(`/movies/${film}`)
    await expect(mark.page.getByRole('button', { name: 'Open disc photo' })).toBeVisible()
    await expect(mark.page.getByRole('button', { name: 'Delete photo' })).toHaveCount(0)
    await expect(mark.page.getByRole('button', { name: 'Take a photo' })).toHaveCount(0)
  })

  test('eBay accounts: Connect sends the person to eBay, the return page finishes it, Disconnect takes it away', async ({ signedIn }) => {
    const mark = await signedIn('Mark')
    // eBay's own sign-in page is outside this app; stand in for it and send the person back
    // with the one-time code and the state the app made.
    let sentTo = ''
    await mark.page.route('https://auth.ebay.com/**', async (route) => {
      const asked = new URL(route.request().url())
      sentTo = asked.origin + asked.pathname
      const state = asked.searchParams.get('state') ?? ''
      return route.fulfill({
        status: 302,
        headers: { location: `${WEB_ORIGIN}/settings/ebay/connected?code=e2e-code&state=${encodeURIComponent(state)}` },
      })
    })
    await mark.page.goto('/settings?tab=ebay')
    await mark.page.getByRole('button', { name: 'Connect eBay' }).click()
    await expect(mark.page.getByText(/eBay is connected/)).toBeVisible()
    expect(sentTo).toBe('https://auth.ebay.com/oauth2/authorize')
    await expect(mark.page.getByText('e2e_collector')).toBeVisible()

    // Disconnecting deletes the app's copy of the sign-in.
    await mark.page.goto('/settings?tab=ebay')
    mark.page.once('dialog', (dialog) => void dialog.accept())
    await mark.page.getByRole('button', { name: 'Disconnect' }).click()
    await expect(mark.page.getByRole('button', { name: 'Connect eBay' })).toBeVisible()
  })
})
