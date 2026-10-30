import { expect, test } from '../support/test.ts'

// These exercise the real production bundle's targeting and geometry, not the native
// iOS compositor. The latter remains an affected-iPhone acceptance observation.
for (const mode of [
  { name: 'Apple Home Screen', apple: true, generic: false },
  { name: 'non-Apple standalone', apple: false, generic: true },
  { name: 'browser without an Apple signal', apple: null, generic: false },
]) {
  test(`AB4 keeps header and Search geometry correct in ${mode.name}`, async ({ signedIn }, testInfo) => {
    const { page, context } = await signedIn('Craig')
    await context.addInitScript(({ apple, generic }) => {
      Object.defineProperty(navigator, 'standalone', { configurable: true, value: apple === null ? undefined : apple })
      const original = window.matchMedia.bind(window)
      window.matchMedia = (query: string) => {
        const result = original(query)
        if (query === '(display-mode: standalone)') Object.defineProperty(result, 'matches', { value: generic })
        return result
      }
    }, mode)
    await page.goto('/dashboard')
    // The document load finishes before auth and the lazy Home graph. Wait for the
    // real screen before asking WebKit to reload it for the first theme.
    await expect(page.getByRole('list', { name: 'The collection in numbers' })).toBeVisible()

    for (const theme of ['dark', 'light']) {
      await page.evaluate(value => localStorage.setItem('mcu-theme', value), theme)
      await page.reload()
      const header = page.getByRole('banner', { name: 'Top bar' })
      await expect(header).toBeVisible()
      await expect(page.getByRole('list', { name: 'The collection in numbers' })).toBeVisible()
      expect(await page.locator('html').getAttribute('data-apple-standalone')).toBe(mode.apple === true ? '' : null)

      for (const viewport of [
        { width: 390, height: 844, inset: 62 },
        { width: 390, height: 568, inset: 62 },
        { width: 844, height: 390, inset: 0 },
        { width: 1023, height: 900, inset: 62 },
        { width: 1024, height: 900, inset: 62 },
      ]) {
        await page.setViewportSize(viewport)
        // Desktop engines expose a zero native inset. Override the shared inset value
        // to prove the actual CSS cascade at both positive and zero inset, not to claim
        // that a simulated device renders Apple's system blur or software keyboard.
        await page.evaluate(inset => document.documentElement.style.setProperty('--mcu-safe-area-top', `${inset}px`), viewport.inset)
        const extra = mode.apple === true && viewport.width < 1024 && viewport.inset > 0 ? 32 : 0
        await expect.poll(() => header.evaluate(element => parseFloat(getComputedStyle(element).paddingTop))).toBe(viewport.inset + extra)
        expect(await header.evaluate(element => getComputedStyle(element).position)).toBe('relative')
        const headerBox = await header.boundingBox()
        const mainBox = await page.getByRole('main').boundingBox()
        expect(headerBox).not.toBeNull()
        expect(mainBox).not.toBeNull()
        expect(mainBox!.y).toBeGreaterThanOrEqual(headerBox!.y + headerBox!.height)
        expect(mainBox!.height).toBeGreaterThan(0)
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)

        if (viewport.width < 1024) {
          if (mode.apple === true && viewport.width === 390 && viewport.height === 844) {
            await page.screenshot({ path: testInfo.outputPath(`ab4-header-${theme}.png`) })
          }
          await page.getByRole('button', { name: 'Search the archive' }).click()
          const sheet = page.getByRole('dialog', { name: 'Search the archive' })
          await expect(sheet.getByRole('combobox', { name: 'Search films' })).toBeFocused()
          await expect.poll(() => sheet.evaluate(element => parseFloat(getComputedStyle(element).paddingTop))).toBe(viewport.inset + extra + 12)
          await page.screenshot({ path: testInfo.outputPath(`ab4-${mode.name}-${theme}-${viewport.width}x${viewport.height}-search.png`) })
          await sheet.getByRole('button', { name: 'Cancel', exact: true }).click()
          await expect(sheet).not.toBeVisible()
        }
      }
    }
  })
}
