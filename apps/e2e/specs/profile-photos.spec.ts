import { filmId } from '../support/films.ts'
import { expect, test } from '../support/test.ts'

const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64')

test('each person chooses a private profile picture, sees it across the app, and can use their initial again', async ({ signedIn, api }, testInfo) => {
  for (const person of ['Craig', 'Mark'] as const) {
    const { page } = await signedIn(person)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/you')
    const account = page.getByRole('region', { name: 'Signed in as' })
    await expect(account).toContainText(person)
    await page.getByLabel('Choose profile picture').setInputFiles({ name: 'me.png', mimeType: 'image/png', buffer: PNG })
    await expect(page.getByRole('status').filter({ hasText: 'Profile picture saved.' })).toBeVisible()
    await expect(account.locator('img')).toHaveAttribute('src', /^blob:/)
    await expect(page.getByRole('link', { name: 'You: every other page, and your account' }).locator('img')).toHaveAttribute('src', /^blob:/)
    expect(await account.locator('img').evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
    await page.screenshot({ path: testInfo.outputPath(`aa7-${person}-375px.png`), fullPage: true })
    const personApi = await api(person)
    const film = await filmId(personApi, 'The Quiet Engine')
    await personApi.post('/watch-log', { movieId: film })
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Recent activity' })).toBeVisible()
    const event = page.getByRole('listitem').filter({ hasText: `${person} watched The Quiet Engine` }).first()
    await expect(event.locator('img[src^="blob:"]')).toBeVisible()
    await page.goto('/movie-night')
    await page.getByRole('button', { name: 'Start movie night' }).click()
    await expect(page.getByRole('main').locator('header img[src^="blob:"]')).toBeVisible()
    await page.goto('/you')
    await page.setViewportSize({ width: 1280, height: 900 })
    await expect(page.getByRole('complementary').locator('img[src^="blob:"]')).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`aa7-${person}-1280px.png`), fullPage: true })
    await page.reload()
    await expect(account.locator('img')).toHaveAttribute('src', /^blob:/)
    await page.getByRole('button', { name: 'Use my initial' }).click()
    await expect(account.locator('img')).toHaveCount(0)
    await expect(account).toContainText(person.slice(0, 1))
  }
})
