import { expect, test } from '../support/test.ts'

// AH1 (#396, #397, #398): both people add, change and remove any want on the shared list. Mark
// finds a film on the Wanted page and adds it; its card reads "Added by you". Craig's want reads
// "Added by Craig" and gives Mark the same controls: he removes both, and the API records Craig's
// removal as Mark's. Until the owner's word on 24 Nov (#398), Mark could not touch Craig's.
test("AH1 Mark adds a want, and removes his own and Craig's", async ({ signedIn, api }) => {
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

    await card('Tidewater Almanac').getByRole('button', { name: 'Remove Tidewater Almanac' }).click()
    await expect(page.getByRole('link', { name: 'Tidewater Almanac', exact: true })).toHaveCount(0)
    await card('Ninefold Kestrel').getByRole('button', { name: 'Remove Ninefold Kestrel' }).click()
    await expect(page.getByRole('link', { name: 'Ninefold Kestrel', exact: true })).toHaveCount(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)

    const audit = await craig.get<{ items: { actorName: string | null }[] }>(
      `/admin/audit?targetTable=wanted_list&targetId=${craigs.id}&actionType=delete`,
    )
    expect(audit.items.map((entry) => entry.actorName)).toEqual(['Mark'])
  } finally {
    // Mark removed it in the case; if the case stopped first, Craig tidies it.
    await craig.call('DELETE', `/wanted/${craigs.id}`, undefined, [204, 404])
  }
})
