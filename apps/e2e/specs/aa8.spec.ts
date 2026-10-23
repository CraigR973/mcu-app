import { expect, test } from '../support/test.ts'

test.describe('AA8 private artwork', () => {
  test('shows the authenticated Home hero at phone and desktop widths', async ({ signedIn }, testInfo) => {
    const { page } = await signedIn('Craig')

    for (const width of [375, 1280]) {
      await page.setViewportSize({ width, height: 844 })
      await page.goto('/dashboard')
      const hero = page.getByRole('img', { name: 'MARKS — five moments from the collection' })
      await expect(hero).toBeVisible()
      await expect(hero).toHaveAttribute('src', /^blob:/)
      await page.screenshot({ path: testInfo.outputPath(`aa8-home-${width}.png`), fullPage: false })
    }
  })
})
