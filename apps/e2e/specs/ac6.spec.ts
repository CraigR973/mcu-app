import { exerciseCinemaDigest } from '../support/cinema-digest.ts'
import { expect, PINS, settleEveryPage, test } from '../support/test.ts'

test('AC6 scheduled cinema digest opens New this week, both themes at 375 px, and retains its settings', async ({ api, signedIn, db, browser }, testInfo) => {
  const fixture = await exerciseCinemaDigest(await api('Craig'), await api('Mark'), db)
  try {
    for (const theme of ['light', 'dark']) {
      const { context, page } = await signedIn('Craig')
      await page.setViewportSize({ width: 375, height: 844 })
      await context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
      await page.goto(fixture.url)
      const section = page.getByRole('region', { name: 'New this week' })
      await expect(section.getByRole('article', { name: 'Ember Coast' })).toBeVisible()
      await expect(section.getByText('Rerun', { exact: true }).first()).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await page.screenshot({ path: testInfo.outputPath(`ac6-${theme}-375.png`) })
      await section.getByRole('link').first().click()
      await expect(page.getByRole('heading', { name: 'Ember Coast', exact: true, level: 1 })).toBeVisible()
      await page.getByRole('button', { name: 'Back', exact: true }).click()
      await expect(page).toHaveURL(/view=new-this-week/)
      await context.close()
    }
    const signedOut = await browser.newContext({ serviceWorkers: 'block' })
    settleEveryPage(signedOut)
    const entry = await signedOut.newPage()
    await entry.goto(fixture.url)
    await entry.getByLabel('Name').fill('Craig')
    await entry.getByLabel('PIN', { exact: true }).fill(PINS.Craig)
    await entry.getByRole('button', { name: 'Enter the archive' }).click()
    await expect(entry).toHaveURL(/view=new-this-week/)
    await expect(entry.getByRole('region', { name: 'New this week' }).getByRole('article', { name: 'Ember Coast' })).toBeVisible()
    await signedOut.close()
    const { page } = await signedIn('Mark')
    await page.goto('/settings/notifications')
    await expect(page.getByRole('switch', { name: 'Cinemas', exact: true })).toHaveAttribute('aria-checked', 'true')
    await expect(page.getByRole('switch', { name: 'Older films only' })).toHaveAttribute('aria-checked', 'true')
    const cinemas = page.getByRole('switch', { name: 'Cinemas', exact: true })
    await cinemas.click()
    // The switch moves only when the server has answered, so this is the save landing. Older films
    // only is disabled while any save is in flight, so on its own it proved nothing: on 10 Nov
    // WebKit's reload cancelled the save it had seen go out (#367).
    await expect(cinemas).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByRole('switch', { name: 'Older films only' })).toBeDisabled()
    await page.reload()
    await expect(page.getByRole('switch', { name: 'Cinemas', exact: true })).toHaveAttribute('aria-checked', 'false')
    await expect(page.getByRole('switch', { name: 'Older films only' })).toHaveAttribute('aria-checked', 'true')
    await expect(page.getByRole('switch', { name: 'Movie night' })).toHaveAttribute('aria-checked', 'true')
  } finally {
    await fixture.cleanup()
  }
})
