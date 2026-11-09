import { randomUUID } from 'node:crypto'
import type { Page } from '@playwright/test'

import { expect, test } from '../support/test.ts'

interface Copy {
  id: string
  movieId: string
  formats: string[]
}

// AE1 (#355, point 10): Mark ticked 4K UHD on Contagion's Blu-ray copy meaning "I bought the 4K
// too", and the app made one combo copy without asking. Ticking a second disc now asks first, and
// "a separate copy" leaves the first copy alone and adds the new one beside it.
/** Nothing wider than the phone: no sideways scroll at 375 px. */
async function fitsThePhone(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}

for (const theme of ['light', 'dark']) {
test(`AE1 a second disc on a copy asks first; a separate copy leaves the first alone and adds a 4K beside it, at 375px in ${theme}`, async ({ signedIn, api }, testInfo) => {
  const mark = await api('Mark'), craig = await api('Craig')
  const title = `AE1 combo ${randomUUID().slice(0, 8)}`
  const first = await mark.post<Copy>('/collection', {
    title,
    formats: ['blu_ray'],
    section: 'Garage',
    location: 'AE1 shelf',
    hasPlaybackIssues: false,
    clientRequestId: randomUUID(),
  })
  const made = [first.id]
  try {
    const { page, context } = await signedIn('Mark')
    await context.addInitScript((value) => localStorage.setItem('mcu-theme', value), theme)
    await page.setViewportSize({ width: 375, height: 844 })
    await page.goto(`/movies/${first.movieId}`)
    await page.getByRole('button', { name: /Edit copy/ }).click()
    await page.getByRole('button', { name: '4K UHD', exact: true }).click()
    await page.getByRole('button', { name: /Save changes/ }).click()

    const question = page.getByRole('alertdialog', { name: 'One box with both discs, or a separate copy?' })
    await expect(question).toContainText('A separate copy leaves this one as Blu-ray and adds the 4K UHD as its own copy.')
    await fitsThePhone(page)
    await page.screenshot({ path: testInfo.outputPath(`ae1-question-${theme}-375.png`) })
    await question.getByRole('button', { name: /A separate copy/ }).click()

    // Add a copy, on the same film, with the 4K chosen; the Blu-ray copy is untouched.
    await expect(page).toHaveURL(new RegExp(`/collection/add\\?movie=${first.movieId}&format=4k_uhd$`))
    await expect(page.getByText('A new copy of this film.')).toBeVisible()
    await expect(page.getByRole('button', { name: '4K UHD', exact: true })).toHaveAttribute('aria-pressed', 'true')
    expect((await mark.get<Copy[]>(`/movies/${first.movieId}/copies`)).map((copy) => copy.formats)).toEqual([['blu_ray']])

    await page.getByRole('combobox', { name: 'Section' }).selectOption({ label: 'Garage' })
    await page.getByRole('textbox', { name: 'Location' }).fill('AE1 shelf')
    // The prompt keeps its meaning: the 4K is an upgrade on the Blu-ray, or a second box.
    await expect(page.getByText('You already own this on Blu-ray')).toBeVisible()
    await fitsThePhone(page)
    await page.getByText('You already own this on Blu-ray').scrollIntoViewIfNeeded()
    await page.screenshot({ path: testInfo.outputPath(`ae1-separate-copy-${theme}-375.png`) })
    const added = page.waitForResponse((r) => r.url().endsWith('/api/v1/collection') && r.request().method() === 'POST')
    await page.getByRole('button', { name: /Add as a separate copy/ }).click()
    const second = (await (await added).json()) as Copy
    made.push(second.id)

    await expect(page.getByRole('main').getByText('2 owned copies')).toBeVisible()
    const formats = (await mark.get<Copy[]>(`/movies/${first.movieId}/copies`)).map((copy) => copy.formats.join('+')).sort()
    expect(formats).toEqual(['4k_uhd', 'blu_ray'])
  } finally {
    for (const id of made) await craig.delete(`/collection/${id}`)
  }
})
}

test('AE1 a new copy starts with no format, and adding without one says to choose', async ({ signedIn }) => {
  const { page } = await signedIn('Craig')
  const title = `AE1 no format ${randomUUID().slice(0, 8)}`
  await page.goto('/collection/add')
  await page.getByRole('tab', { name: /Search title/ }).click()
  await page.getByRole('textbox', { name: 'Search for a film' }).fill(title)
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await page.getByRole('button', { name: `Add “${title}” by its title` }).click()

  const formats = page.getByRole('group', { name: 'Formats' })
  await expect(formats.getByRole('button', { pressed: true })).toHaveCount(0)
  let posted = 0
  page.on('request', (r) => {
    if (r.url().endsWith('/api/v1/collection') && r.method() === 'POST') posted += 1
  })
  await page.getByRole('button', { name: `Add “${title}”`, exact: true }).click()
  await expect(page.getByRole('alert').filter({ hasText: 'Choose a format' })).toHaveText('Choose a format: 4K UHD, Blu-ray, DVD or Digital.')
  expect(posted).toBe(0)
})
