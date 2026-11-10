import type { Api } from '../support/api.ts'
import { filmId } from '../support/films.ts'
import { expect, test } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
const day = (offset: number) => new Date(Date.now() + offset * 86400000).toISOString().slice(0, 10)

async function copyOf(api: Api, title: string): Promise<string> {
  const copies = await api.get<{ id: string }[]>(`/movies/${await filmId(api, title)}/copies`)
  const first = copies[0]
  if (!first) throw new Error(`no copy of ${title}`)
  return first.id
}

// AE9 (#355): a page for each person, read-only. Mark has had The Lighthouse Keeper for 20 days,
// so Craig's Needs you labels it Mark's, and the label opens Mark's page; Mark's own label opens
// You. Each reads the other's page at 375 px in both themes, and no setting is on it.
test('AE9 a Needs you label opens that person’s page, your own opens You, at 375 px in both themes', async ({ signedIn, api, db }, testInfo) => {
  const craig = await api('Craig')
  const mark = await api('Mark')
  const markId = (await mark.get<{ id: string }>('/auth/me')).id
  const craigId = (await craig.get<{ id: string }>('/auth/me')).id
  const lent = await craig.post<{ id: string }>('/loans', { collectionItemId: await copyOf(craig, 'The Lighthouse Keeper'), borrowerProfileId: markId, lentDate: day(-20) })
  try {
    for (const theme of ['light', 'dark'] as const) {
      // Craig: the label on Mark's loan opens Mark's page.
      const craigs = await signedIn('Craig')
      await craigs.page.setViewportSize({ width: 375, height: 812 })
      await craigs.context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
      await craigs.page.goto('/dashboard')
      const row = craigs.page.getByRole('region', { name: /Needs you/ })
      const item = row.getByRole('listitem').filter({ hasText: 'The Lighthouse Keeper' })
      await item.getByRole('link', { name: 'Mark’s: open their page' }).click()
      await expect(craigs.page).toHaveURL(new RegExp(`/people/${markId}$`))
      await expect(craigs.page.getByRole('heading', { level: 1, name: 'Mark' })).toBeVisible()
      const has = craigs.page.getByRole('region', { name: 'Has now' })
      await expect(has.getByRole('link', { name: /The Lighthouse Keeper/ })).toBeVisible()
      for (const section of ['Lately in the diary', 'Added lately', 'Wants']) {
        await expect(craigs.page.getByRole('region', { name: section })).toBeVisible()
      }
      await expect(craigs.page.getByText(/\bPIN\b|Notifications|Connect eBay/)).toHaveCount(0)
      expect(await craigs.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await craigs.page.screenshot({ path: testInfo.outputPath(`ae9-mark-by-craig-${theme}-375.png`), fullPage: true })
      await craigs.context.close()

      // Mark: his own label opens You; Craig's page is his to read.
      const marks = await signedIn('Mark')
      await marks.page.setViewportSize({ width: 375, height: 812 })
      await marks.context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
      await marks.page.goto('/dashboard')
      const own = marks.page.getByRole('region', { name: /Needs you/ }).getByRole('listitem').filter({ hasText: 'The Lighthouse Keeper' })
      await own.getByRole('link', { name: 'Yours: open You' }).click()
      await expect(marks.page).toHaveURL(/\/you$/)
      await marks.page.goto(`/people/${markId}`)
      await expect(marks.page).toHaveURL(/\/you$/)
      await marks.page.goto(`/people/${craigId}`)
      await expect(marks.page.getByRole('heading', { level: 1, name: 'Craig' })).toBeVisible()
      expect(await marks.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
      await marks.page.screenshot({ path: testInfo.outputPath(`ae9-craig-by-mark-${theme}-375.png`), fullPage: true })
      await marks.context.close()
    }
  } finally {
    db.sql(`DELETE FROM loans WHERE id=${sql(lent.id)}`)
  }
})
