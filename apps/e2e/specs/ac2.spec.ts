import { expect, test } from '../support/test.ts'

// AC2 (#337): Home as Craig picked it, direction A with banner T1 and Feeling lucky inside the
// featured film, for both people, at 375 and 320 px, in both themes.
for (const person of ['Craig', 'Mark'] as const) {
  test(`AC2 Home is one ledger, one featured film, at most four rows and no film twice, for ${person}`, async ({ signedIn }, testInfo) => {
    const { page, context } = await signedIn(person)
    for (const theme of ['light', 'dark'] as const) {
      await context.addInitScript((value) => localStorage.setItem('mcu-theme', value), theme)
      for (const width of [375, 320]) {
        await page.setViewportSize({ width, height: 812 })
        await page.goto('/dashboard')
        const main = page.getByRole('main')
        await expect(main.getByRole('list', { name: 'The collection in numbers' })).toBeVisible()
        const banner = main.getByRole('img', { name: "MARK'S Cinematic Universe" })
        await expect(banner).toBeVisible()
        await expect(banner.locator('img')).toHaveAttribute('src', /^data:image\/webp/)
        await expect(banner).toContainText('Cinematic Universe')
        const lucky = main.getByRole('group', { name: 'Feeling lucky' })
        await expect(lucky.getByRole('button', { name: /^Deal (a film|another)$/ })).toBeEnabled()
        await expect(main.getByText('Matched on TMDB')).toHaveCount(0)
        await expect(main.getByRole('tab', { name: 'Top rated' })).toHaveCount(0)
        const sideways = await main.locator('ul.overflow-x-auto').count()
        expect(sideways, 'sideways rows').toBeLessThanOrEqual(4)
        const films = await main.locator('a[href^="/movies/"]').evaluateAll((links) => links.map((link) => link.getAttribute('href')))
        const repeated = films.filter((href, index) => films.indexOf(href) !== index)
        expect(repeated, 'a film shown twice on Home').toEqual([])
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), `${String(width)} px fits`).toBe(true)
        await page.setViewportSize({ width, height: 2600 })
        await page.screenshot({ path: testInfo.outputPath(`ac2-${person}-${theme}-${String(width)}.png`), fullPage: true })
      }
    }
  })
}

test('AC2 keeps the banner on the device after its first load, and forgets it at sign-out', async ({ signedIn }) => {
  const { page } = await signedIn('Mark')
  await page.setViewportSize({ width: 375, height: 812 })
  const fetched: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/brand/heroes/')) fetched.push(request.url())
  })
  await page.goto('/dashboard')
  await expect(page.getByRole('img', { name: "MARK'S Cinematic Universe" }).locator('img')).toHaveAttribute('src', /^data:image\/webp/)
  expect(fetched).toHaveLength(1)
  expect(fetched[0]).toMatch(/\/brand\/heroes\/letters-v1-1125$/)
  await page.reload()
  // Drawn straight from the device: the artwork is there on the first frame, with no request.
  await expect(page.getByRole('img', { name: "MARK'S Cinematic Universe" }).locator('img')).toHaveAttribute('src', /^data:image\/webp/)
  expect(fetched).toHaveLength(1)
  await page.getByRole('link', { name: 'You: every other page, and your account' }).click()
  await page.getByRole('main').getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByLabel('Name')).toBeVisible()
  expect(await page.evaluate(() => Object.keys(localStorage).filter((key) => key.startsWith('mcu.banner.')))).toEqual([])
})
