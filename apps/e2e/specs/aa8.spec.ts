import { expect, test } from '../support/test.ts'

test.describe('AA8 private artwork', () => {
  // AC2 (#337): the Home hero is banner T1, the photo letters alone, still fetched only with the
  // person's token and never a public file. It is kept on the device as a data URL, where AA8's
  // version made an object URL on every visit; each width asks for the size it needs.
  test('shows the authenticated Home hero at phone and desktop widths', async ({ signedIn }, testInfo) => {
    const { page } = await signedIn('Craig')
    const asked: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/brand/')) asked.push(new URL(request.url()).pathname)
    })

    for (const [width, size] of [[375, 1125], [1280, 1800]] as const) {
      await page.setViewportSize({ width, height: 844 })
      await page.goto('/dashboard')
      const hero = page.getByRole('img', { name: "MARK'S Cinematic Universe" })
      await expect(hero).toBeVisible()
      await expect(hero.locator('img')).toHaveAttribute('src', /^data:image\/webp/)
      expect(asked).toContain(`/api/v1/brand/heroes/letters-v1-${String(size)}`)
      await page.screenshot({ path: testInfo.outputPath(`aa8-home-${width}.png`), fullPage: false })
    }
    // Only the authenticated API route: no hero is fetched from the public web assets.
    expect(asked.filter((path) => path.startsWith('/brand/') && path.includes('hero'))).toEqual([])
  })
})
