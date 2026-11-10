import { expect, test } from '../support/test.ts'

// AC2: Home's banner weight and layout shift, measured the same way before and after the
// redesign, and held there. Before (4 Nov, Chromium, 375 px): a 2,057,722-byte banner and a
// layout shift of 0.234 for Craig, 0.219 for Mark. Layout-shift entries exist only in
// Chromium, so the shift is held there; the bytes are held in every browser.
test('Home measures its banner bytes and its layout shift while the first layout arrives', async ({ signedIn, browserName }, testInfo) => {
  for (const person of ['Craig', 'Mark'] as const) {
    const { page } = await signedIn(person)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.addInitScript(() => {
      const w = window as unknown as { __shift: number }
      w.__shift = 0
      try {
        new PerformanceObserver((list) => {
          for (const entry of list.getEntries() as unknown as { value: number; hadRecentInput: boolean }[]) {
            if (!entry.hadRecentInput) w.__shift += entry.value
          }
        }).observe({ type: 'layout-shift', buffered: true })
      } catch {
        /* no layout-shift entries in this browser */
      }
    })
    const banners: Promise<number>[] = []
    page.on('response', (response) => {
      if (response.url().includes('/api/v1/brand/heroes/') && response.request().method() === 'GET') {
        // The declared length: a fetch's body is not always readable from here once the page has it.
        banners.push(Promise.resolve(Number(response.headers()['content-length'] ?? 0)))
      }
    })
    await page.goto('/dashboard')
    await expect(page.getByRole('list', { name: 'The collection in numbers' })).toBeVisible()
    // Home holds a live connection open, so wait until it stops changing: the same shift and
    // resource count twice running, with every image decoded.
    let last = ''
    await expect.poll(async () => {
      const now = await page.evaluate(() => JSON.stringify([
        (window as unknown as { __shift: number }).__shift,
        performance.getEntriesByType('resource').length,
        // Settled means the first layout's images, not a lazy poster below the fold that the page
        // has not asked for: Firefox reports one of those incomplete until it is scrolled to, and
        // since AE2 Home's Highlights opens on Recently added's posters there.
        Array.from(document.images).every((image) => image.complete || (image.loading === 'lazy' && image.getBoundingClientRect().top >= innerHeight)),
      ]))
      const settled = now === last && now.endsWith('true]')
      last = now
      return settled
    }, { intervals: [500, 500, 750, 1000], timeout: 20_000 }).toBe(true)
    const shift = await page.evaluate(() => (window as unknown as { __shift: number }).__shift)
    const bannerBytes = (await Promise.all(banners)).reduce((sum, bytes) => sum + bytes, 0)
    testInfo.annotations.push({ type: `${person} ${browserName}`, description: `banner ${String(bannerBytes)} B, layout shift ${shift.toFixed(4)}` })
    console.log(`AC2-MEASURE ${person} ${browserName} banner=${String(bannerBytes)}B shift=${shift.toFixed(4)}`)
    expect(bannerBytes).toBeGreaterThan(0)
    expect(bannerBytes, 'banner T1 at most 200 KB').toBeLessThanOrEqual(200 * 1024)
    if (browserName === 'chromium') expect(shift, 'a layout shift Google calls good').toBeLessThan(0.1)
  }
})
