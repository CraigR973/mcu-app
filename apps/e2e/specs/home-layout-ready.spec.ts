import { expect, test } from '../support/test.ts'

test('Home waits for the collection layout before accepting a pick or cinema navigation', async ({ signedIn, db }) => {
  const watches = db.scalar('SELECT count(*) FROM watch_log')
  for (const person of ['Craig', 'Mark'] as const) {
    const { page } = await signedIn(person)
    await page.setViewportSize({ width: 375, height: 812 })
    let release!: () => void
    let received!: () => void
    const held = new Promise<void>(resolve => { release = resolve })
    const ready = new Promise<void>(resolve => { received = resolve })
    let statsRequests = 0
    await page.route('**/api/v1/collection/stats', async route => {
      statsRequests += 1
      const response = await route.fetch()
      expect(response.status()).toBe(200)
      received()
      await held
      await route.fulfill({ response })
    })
    try {
      await page.goto('/dashboard')
      await ready
      const lucky = page.getByRole('group', { name: 'Feeling lucky' })
      const checkbox = lucky.getByRole('checkbox', { name: 'Only films I haven’t watched' })
      const cinemas = page.getByRole('link', { name: 'At the cinema', exact: true })
      await expect(checkbox).toBeDisabled()
      // AC2: Feeling lucky lives in the featured film; its deal reads "Deal another" when a film is shown.
      await expect(lucky.getByRole('button', { name: /^Deal (a film|another)$/ })).toBeDisabled()
      await expect(cinemas).toHaveAttribute('aria-disabled', 'true')
      release()
      await expect(page.getByRole('list', { name: 'The collection in numbers' })).toBeVisible()
      await expect(checkbox).toBeEnabled()
      await checkbox.check()
      await expect(checkbox).toBeChecked()
      await expect(cinemas).not.toHaveAttribute('aria-disabled', 'true')
      await cinemas.click()
      await expect(page).toHaveURL(/\/cinemas$/)
      expect(statsRequests, 'both observers must share the existing stats request').toBe(1)
    } finally { release() }
  }
  expect(db.scalar('SELECT count(*) FROM watch_log')).toBe(watches)
})
