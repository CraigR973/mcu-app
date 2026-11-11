import { expect, test } from '../support/test.ts'

// DECISIONS.md #367. WebKit cancels everything a page has in flight the moment a navigation
// starts, so the harness lets a page settle before any navigation a case asks for. Made certain
// here, not left to timing: the save is held at the network until the reload has been asked for.
// A reload that did not wait would go first, and in WebKit it would cancel the save outright.
test('a reload asked for while a save is still out waits for its answer, so the save lands', async ({ signedIn, api }) => {
  const mark = await api('Mark')
  const before = await mark.get<{ digestMode: boolean }>('/notifications/preferences')
  const { page } = await signedIn('Mark')
  try {
    await page.goto('/settings/notifications')
    const digest = page.getByRole('switch', { name: 'Daily digest', exact: true })
    await expect(digest).toHaveAttribute('aria-checked', String(before.digestMode))

    const order: string[] = []
    page.on('response', (response) => {
      if (response.request().method() === 'PUT' && response.url().endsWith('/api/v1/notifications/preferences')) {
        order.push(`save answered ${response.status()}`)
      }
    })
    page.on('request', (request) => {
      if (request.isNavigationRequest() && request.frame() === page.mainFrame()) order.push('reload')
    })
    let release!: () => void
    const held = new Promise<void>((resolve) => (release = resolve))
    let sent!: () => void
    const out = new Promise<void>((resolve) => (sent = resolve))
    await page.route('**/api/v1/notifications/preferences', async (route) => {
      if (route.request().method() !== 'PUT') return route.continue()
      sent()
      await held
      return route.continue()
    })

    await digest.click()
    await out
    const reloading = page.reload()
    release()
    await reloading

    expect(order).toEqual(['save answered 200', 'reload'])
    await expect(page.getByRole('switch', { name: 'Daily digest', exact: true })).toHaveAttribute('aria-checked', String(!before.digestMode))
  } finally {
    await mark.put('/notifications/preferences', { digestMode: before.digestMode })
  }
})
