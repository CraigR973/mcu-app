import { expect, test } from '../support/test.ts'

async function topBarColours(page: import('@playwright/test').Page) {
  return page.getByRole('banner', { name: 'Top bar' }).evaluate((bar) => ({
    background: getComputedStyle(bar).backgroundColor,
    page: getComputedStyle(document.body).backgroundColor,
    bottomRule: getComputedStyle(bar).borderBottomColor,
  }))
}

test.describe('AA1 quick fixes', () => {
  test('the 375 px top bar uses the page surface, with a visible rule, in both themes', async ({ signedIn }, testInfo) => {
    const { context, page } = await signedIn('Craig')
    await page.setViewportSize({ width: 375, height: 844 })

    for (const theme of ['dark', 'light'] as const) {
      await context.addInitScript((value) => localStorage.setItem('mcu-theme', value), theme)
      await page.goto('/dashboard')
      const bar = page.getByRole('banner', { name: 'Top bar' })
      await expect(bar.getByRole('heading', { name: 'Home', level: 1 })).toBeVisible()

      const colours = await topBarColours(page)
      expect(colours.background, `${theme} top bar`).toBe(colours.page)
      expect(colours.bottomRule, `${theme} top-bar rule`).not.toBe(colours.background)

      if (theme === 'dark') {
        // A controlled rendering of AA1's previous token gives Craig the requested
        // before/after comparison without changing the app under test.
        await bar.evaluate((element) => element.classList.replace('bg-background', 'bg-popover'))
        await page.screenshot({ path: testInfo.outputPath('aa1-top-bar-before-dark.png'), clip: { x: 0, y: 0, width: 375, height: 110 } })
        await bar.evaluate((element) => element.classList.replace('bg-popover', 'bg-background'))
        await page.screenshot({ path: testInfo.outputPath('aa1-top-bar-after-dark.png'), clip: { x: 0, y: 0, width: 375, height: 110 } })
      }
    }
  })
})
