import { expect, test } from '../support/test.ts'

// AH1 (#396, #397): both people add to the shared wanted list. Mark finds a film on the Wanted
// page and adds it; its card reads "Added by you", and he removes it. Craig's want reads "Added
// by Craig" with nothing for Mark to press, and the API refuses Mark's remove, naming Craig.
test("AH1 Mark adds a want and removes it, and cannot remove Craig's", async ({ signedIn, api }) => {
  const craig = await api('Craig')
  const craigs = await craig.post<{ id: string }>('/wanted', { tmdbId: 1802 }) // Tidewater Almanac
  try {
    const { page } = await signedIn('Mark')
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/wanted')

    const adding = page.getByRole('region', { name: 'Add a wanted film' })
    await adding.getByLabel('Search for a wanted film').fill('Ninefold Kestrel')
    await adding.getByRole('button', { name: 'Search', exact: true }).click()
    await adding.getByRole('listitem').filter({ hasText: 'Ninefold Kestrel' }).getByRole('button', { name: 'Add' }).click()

    const card = (title: string) => page.getByRole('listitem').filter({ has: page.getByRole('link', { name: title, exact: true }) })
    await expect(card('Ninefold Kestrel')).toContainText('Added by you')
    await expect(card('Tidewater Almanac')).toContainText('Added by Craig')
    await expect(card('Tidewater Almanac').getByRole('button')).toHaveCount(0)

    const mark = await api('Mark')
    const refused = await mark.call<{ detail: string }>('DELETE', `/wanted/${craigs.id}`, undefined, [403])
    expect(refused.detail).toContain('Craig')

    await card('Ninefold Kestrel').getByRole('button', { name: 'Remove Ninefold Kestrel' }).click()
    await expect(page.getByRole('link', { name: 'Ninefold Kestrel', exact: true })).toHaveCount(0)
    await expect(card('Tidewater Almanac')).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  } finally {
    await craig.delete(`/wanted/${craigs.id}`)
  }
})
