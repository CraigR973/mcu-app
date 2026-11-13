import type { Api } from '../support/api.ts'
import { filmId } from '../support/films.ts'
import { expect, test } from '../support/test.ts'

/** A date this many days before today, as the API's own UTC date. */
function daysAgo(days: number): string {
  return new Date(Date.now() - days * 86400000).toISOString().slice(0, 10)
}

async function copyOf(api: Api, title: string): Promise<string> {
  const copies = await api.get<{ id: string }[]>(`/movies/${await filmId(api, title)}/copies`)
  const first = copies[0]
  if (!first) throw new Error(`no copy of ${title}`)
  return first.id
}

// AC1 (#335): two films no other case lends, so the order of cases stays free.
test('Needs you gives each person their own jobs, opens the exact place, and clears for both once shelved', async ({ signedIn, api }, testInfo) => {
  const craig = await api('Craig')
  const me = await craig.get<{ id: string }>('/auth/me')
  // Craig has had Glass Orchard for 20 days with no due date, and has brought Paper Moons back.
  await craig.post('/loans', { collectionItemId: await copyOf(craig, 'Glass Orchard'), borrowerProfileId: me.id, lentDate: daysAgo(20) })
  const moons = await craig.post<{ id: string }>('/loans', { collectionItemId: await copyOf(craig, 'Paper Moons Over Leeds'), borrowerProfileId: me.id, lentDate: daysAgo(6) })
  await craig.put(`/loans/${moons.id}/return`, {})

  const { context, page: markPage } = await signedIn('Mark')
  await markPage.setViewportSize({ width: 375, height: 812 })
  for (const theme of ['light', 'dark'] as const) {
    await context.addInitScript((value) => localStorage.setItem('mcu-theme', value), theme)
    await markPage.goto('/dashboard')
    const row = markPage.getByRole('region', { name: /Needs you/ })
    await expect(row.getByRole('link', { name: /Put back Paper Moons Over Leeds/ })).toBeVisible()
    await expect(row.getByRole('link', { name: /Ask Craig for Glass Orchard/ })).toContainText('Lent')
    await expect(row.getByRole('link', { name: /Ask Craig for Glass Orchard/ })).toContainText('out 20 days, no due date')
    // Mark keeps the shelves but none of Craig's app problems: no App rows (AF1, #372).
    await expect(row.getByText('App', { exact: true })).toHaveCount(0)
    await expect(markPage.getByRole('heading', { name: 'Needs attention' })).toHaveCount(0)
    await row.screenshot({ path: testInfo.outputPath(`ac1-mark-${theme}-375.png`) })
  }

  const { page: craigPage } = await signedIn('Craig')
  await craigPage.setViewportSize({ width: 375, height: 812 })
  await craigPage.goto('/dashboard')
  const craigRow = craigPage.getByRole('region', { name: /Needs you/ })
  await expect(craigRow.getByRole('link', { name: /Give back Glass Orchard/ })).toContainText("You've had it since")
  // AF1 (#372): Mark puts every disc back, so Craig reads it as Mark's, after his own.
  await expect(craigRow.getByRole('link', { name: /Mark to put back Paper Moons Over Leeds/ })).toBeVisible()
  await expect(craigRow.getByRole('listitem').filter({ hasText: 'Mark to put back Paper Moons Over Leeds' }).getByRole('link', { name: 'Mark’s: open their page' })).toBeVisible()

  // Mark taps his job: Loans opens on To put back with that disc's own confirm flow open.
  await markPage.getByRole('region', { name: /Needs you/ }).getByRole('link', { name: /Put back Paper Moons Over Leeds/ }).click()
  await expect(markPage).toHaveURL(/\/loans\?view=back&loan=/)
  await expect(markPage.getByRole('button', { name: 'To put back', exact: true })).toHaveAttribute('aria-pressed', 'true')
  const form = markPage.getByRole('form', { name: 'Put back Paper Moons Over Leeds' })
  await expect(form).toBeVisible()
  await form.getByLabel('Change shelf').check()
  await form.getByLabel('Section', { exact: true }).selectOption('Front')
  await form.getByLabel('Shelf or side (optional)').fill('4th')
  await form.getByRole('button', { name: 'Confirm shelved', exact: true }).click()
  await expect(markPage.getByText('Nothing to put back')).toBeVisible()

  // Gone for both of them; Craig's own loan is still his to give back.
  await markPage.goto('/dashboard')
  await expect(markPage.getByRole('region', { name: /Needs you/ }).getByRole('link', { name: /Ask Craig for Glass Orchard/ })).toBeVisible()
  await expect(markPage.getByRole('link', { name: /Put back Paper Moons Over Leeds/ })).toHaveCount(0)
  await craigPage.reload()
  await expect(craigPage.getByRole('region', { name: /Needs you/ }).getByRole('link', { name: /Give back Glass Orchard/ })).toBeVisible()
  await expect(craigPage.getByRole('link', { name: /put back Paper Moons Over Leeds/i })).toHaveCount(0)
  const loans = await craig.get<{ items: { id: string; movieTitle: string; state: string; section: string | null; shelf: string | null }[] }>('/loans')
  expect(loans.items.find((loan) => loan.id === moons.id)).toMatchObject({ state: 'shelved', section: 'Front', shelf: '4th' })

  // Leave the shelves as every other case expects them: nothing out, nothing to put back.
  const glass = loans.items.find((loan) => loan.movieTitle === 'Glass Orchard' && loan.state === 'out')
  if (!glass) throw new Error('Glass Orchard should still be out')
  await craig.put(`/loans/${glass.id}/return`, {})
  await craig.patch(`/loans/${glass.id}`, { state: 'shelved' })
  await craigPage.reload()
  await expect(craigPage.getByRole('list', { name: 'The collection in numbers' })).toBeVisible()
  // Nothing of these loans is left for Craig. His Needs you can still hold the app's problems
  // (App rows, AF1 #372), so it is the loans' rows that are gone, not the card.
  await expect(craigPage.getByRole('region', { name: /Needs you/ }).getByRole('listitem').filter({ hasText: /Glass Orchard|Paper Moons Over Leeds/ })).toHaveCount(0)
})
