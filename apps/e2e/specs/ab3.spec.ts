import { randomUUID } from 'node:crypto'
import { pushesTo, registerDevice } from '../support/push.ts'
import { expect, test } from '../support/test.ts'

type Copy = { id: string; movieId: string }

for (const theme of ['light', 'dark']) {
  test(`AB3 preference wording and persistence at 375px in ${theme}`, async ({ signedIn, api }, testInfo) => {
    const craig = await api('Craig')
    const original = await craig.get<Record<string, unknown>>('/notifications/preferences')
    await craig.put('/notifications/preferences', { collectionAdditionsEnabled: true })
    const { page, context } = await signedIn('Craig')
    await context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
    await page.setViewportSize({ width: 375, height: 844 })
    try {
      await page.goto('/settings')
      const toggle = page.getByRole('switch', { name: "Mark's additions" })
      await expect(toggle).toBeChecked()
      await expect(page.getByText('When Mark adds the first owned copy of a film or series. Extra copies and editions stay quiet.')).toBeVisible()
      await toggle.scrollIntoViewIfNeeded()
      await page.getByRole('heading', { name: 'What you hear about' }).locator('..').screenshot({ path: testInfo.outputPath(`ab3-preference-${theme}-375.png`) })
      await toggle.click()
      await expect.poll(async () => (await craig.get<{ collectionAdditionsEnabled: boolean }>('/notifications/preferences')).collectionAdditionsEnabled).toBe(false)
      await page.reload()
      await expect(page.getByRole('switch', { name: "Mark's additions" })).not.toBeChecked()
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    } finally {
      await craig.put('/notifications/preferences', { collectionAdditionsEnabled: original.collectionAdditionsEnabled })
    }
  })
}

test('AB3 Mark adds through the screen; Craig receives one decrypted push, retries and editions stay quiet', async ({ signedIn, api }) => {
  const craig = await api('Craig'), mark = await api('Mark')
  const old = await craig.get<Record<string, unknown>>('/notifications/preferences')
  await craig.put('/notifications/preferences', { collectionAdditionsEnabled: true, digestMode: false, clearQuietHours: true })
  const craigPhone = await registerDevice(craig, 'ab3-craig'), markPhone = await registerDevice(mark, 'ab3-mark')
  const title = `AB3 shelf ${randomUUID().slice(0, 8)}`
  const { page } = await signedIn('Mark')
  const added: Copy[] = []
  try {
    await page.goto('/collection/add')
    await page.getByRole('tab', { name: /Search title/ }).click()
    await page.getByRole('textbox', { name: 'Search for a film' }).fill(title)
    await page.getByRole('button', { name: 'Search', exact: true }).click()
    await page.getByRole('button', { name: `Add “${title}” by its title` }).click()
    const request = page.waitForRequest(r => r.url().endsWith('/api/v1/collection') && r.method() === 'POST')
    await page.getByRole('button', { name: `Add “${title}”`, exact: true }).click()
    const submitted = await request
    const payload = submitted.postDataJSON() as Record<string, unknown>
    expect(payload.clientRequestId).toMatch(/^[0-9a-f-]{36}$/)
    await expect(page.getByRole('main').getByRole('heading', { name: title, exact: true })).toBeVisible()
    const copy = await mark.post<Copy>('/collection', payload)
    added.push(copy)
    expect(pushesTo(craigPhone).filter(push => push.title === 'Mark added a title')).toEqual([
      expect.objectContaining({ title: 'Mark added a title', body: `${title} is now in the collection.`, url: `/movies/${copy.movieId}` }),
    ])
    expect(pushesTo(markPhone).filter(push => push.title === 'Mark added a title')).toEqual([])
    const extra = await mark.post<Copy>('/collection', { movieId: copy.movieId, formats: ['dvd'], confirmDuplicate: 'another_copy', clientRequestId: randomUUID() })
    added.push(extra)
    expect(pushesTo(craigPhone).filter(push => push.title === 'Mark added a title')).toHaveLength(1)
    const { page: recipient } = await signedIn('Craig')
    await recipient.goto(`/movies/${copy.movieId}`)
    await expect(recipient.getByRole('main').getByRole('heading', { name: title, exact: true })).toBeVisible()
  } finally {
    for (const item of added) await craig.delete(`/collection/${item.id}`)
    await craig.put('/notifications/preferences', { collectionAdditionsEnabled: old.collectionAdditionsEnabled, digestMode: old.digestMode,
      ...(old.quietHoursStart ? { quietHoursStart: old.quietHoursStart, quietHoursEnd: old.quietHoursEnd } : { clearQuietHours: true }) })
  }
})

test('AB3 old preference responses show unavailable without assuming on or off', async ({ signedIn }) => {
  const { page } = await signedIn('Craig')
  await page.route('**/api/v1/notifications/preferences', async route => {
    const response = await route.fetch()
    const body = await response.json() as Record<string, unknown>
    delete body.collectionAdditionsEnabled
    await route.fulfill({ response, json: body })
  })
  await page.goto('/settings')
  await expect(page.getByText('Unavailable — refresh settings')).toBeVisible()
  await expect(page.getByRole('switch', { name: "Mark's additions" })).toHaveCount(0)
})
