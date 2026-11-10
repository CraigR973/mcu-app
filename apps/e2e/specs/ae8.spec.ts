import type { Api } from '../support/api.ts'
import { filmId } from '../support/films.ts'
import { expect, test } from '../support/test.ts'

const sql = (value: unknown) => `'${String(value).replaceAll("'", "''")}'`
/** A date this many days from today (negative: before), as the API's own UTC date. */
const day = (offset: number) => new Date(Date.now() + offset * 86400000).toISOString().slice(0, 10)

async function copyOf(api: Api, title: string): Promise<string> {
  const copies = await api.get<{ id: string }[]>(`/movies/${await filmId(api, title)}/copies`)
  const first = copies[0]
  if (!first) throw new Error(`no copy of ${title}`)
  return first.id
}

// AE8 (#355): the two people who keep the shelves share one Needs you, each item saying whose it
// is, their own first. Mark has had Night Train to Lisbon Docks for 20 days with no due date: his
// to give back, Craig's to ask him for. Mark has asked for Copper Canyon: Craig's to hand over.
// Two films no other case lends.
test('AE8 Craig and Mark see one Needs you, each item labelled, their own first, at 375 px in both themes', async ({ signedIn, api, db }, testInfo) => {
  const craig = await api('Craig')
  const mark = await api('Mark')
  const markId = (await mark.get<{ id: string }>('/auth/me')).id
  const lent = await craig.post<{ id: string }>('/loans', { collectionItemId: await copyOf(craig, 'Night Train to Lisbon Docks'), borrowerProfileId: markId, lentDate: day(-20) })
  const asked = await mark.post<{ id: string }>('/loans', { collectionItemId: await copyOf(mark, 'Copper Canyon'), borrowerProfileId: markId, state: 'asked_for', neededBy: day(3) })
  try {
    for (const [person, own, other, owner] of [
      ['Craig', /^Hand over Copper Canyon/, /^Ask Mark for Night Train to Lisbon Docks/, 'Mark'],
      ['Mark', /^Give back Night Train to Lisbon Docks/, /^Craig to hand over Copper Canyon/, 'Craig'],
    ] as const) {
      for (const theme of ['light', 'dark'] as const) {
        const { context, page } = await signedIn(person)
        await page.setViewportSize({ width: 375, height: 812 })
        await context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
        await page.goto('/dashboard')
        const row = page.getByRole('region', { name: /Needs you/ })
        // Each says whose it is: the reader's own "You", the other's by name (since AE9 a link).
        const item = (name: RegExp) => row.getByRole('listitem').filter({ has: page.getByRole('link', { name }) })
        await expect(item(own).getByRole('link', { name: 'Yours: open You' })).toHaveText('You')
        await expect(item(other).getByRole('link', { name: `${owner}’s: open their page` })).toHaveText(owner)
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        await row.screenshot({ path: testInfo.outputPath(`ae8-home-${person.toLowerCase()}-${theme}-375.png`) })

        // Needs you lists every item for both, the reader's own first.
        await page.goto('/needs-you')
        const all = page.getByRole('region', { name: 'Everything waiting' })
        const listed = (name: RegExp) => all.getByRole('listitem').filter({ has: page.getByRole('link', { name }) })
        await expect(listed(own).getByRole('link', { name: 'Yours: open You' })).toHaveText('You')
        await expect(listed(other).getByRole('link', { name: `${owner}’s: open their page` })).toHaveText(owner)
        const titles = await all.getByRole('link').allTextContents()
        expect(titles.findIndex(text => own.test(text))).toBeLessThan(titles.findIndex(text => other.test(text)))
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
        await page.screenshot({ path: testInfo.outputPath(`ae8-needs-you-${person.toLowerCase()}-${theme}-375.png`), fullPage: true })
        await context.close()
      }
    }
  } finally {
    db.sql(`DELETE FROM loans WHERE id IN (${sql(lent.id)}, ${sql(asked.id)})`)
  }
})
