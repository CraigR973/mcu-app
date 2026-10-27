import { expect, test } from '../support/test.ts'
import type { Person } from '../harness/env.ts'

type Counts = {
  totalItems: number
  downloadCopies: number
  physicalCopies: number
  physicalAndDownloadCopies: number
  watchedMovies: number
  identifiedMovies: number
}

test('AA3 counts a mixed-format combo once as physical and once as download', async ({ api }) => {
  const craig = await api('Craig')
  const before = await craig.get<Counts>('/collection/stats')
  await craig.post('/collection', {
    tmdbId: 1701,
    formats: ['4k_uhd', 'blu_ray', 'download'],
    section: 'Front', shelf: '2nd', hasPlaybackIssues: false,
  })
  for (const person of ['Craig', 'Mark'] as Person[]) {
    const after = await (await api(person)).get<Counts>('/collection/stats')
    expect(after.totalItems).toBe(before.totalItems + 1)
    expect(after.physicalCopies).toBe(before.physicalCopies + 1)
    expect(after.downloadCopies).toBe(before.downloadCopies + 1)
    expect(after.physicalAndDownloadCopies).toBe(before.physicalAndDownloadCopies + 1)
  }
})

for (const person of ['Craig', 'Mark'] as Person[]) {
  test(`AA3 keeps all five meanings and the breakdown reachable for ${person}`, async ({ signedIn, api }, testInfo) => {
    const { page, context } = await signedIn(person)
    const stats = await (await api(person)).get<Counts>('/collection/stats')
    for (const theme of ['dark', 'light']) {
      await context.addInitScript((value) => localStorage.setItem('mcu-theme', value), theme)
      for (const width of [375, 1280]) {
        await page.setViewportSize({ width, height: 844 })
        await page.goto('/dashboard')
        const section = page.getByRole('region', { name: 'The collection', exact: true })
        const numbers = section.getByRole('list', { name: 'The collection in numbers' })
        for (const label of ['Titles owned', 'Copies catalogued', 'Estimated used value', "You've watched", 'Matched on TMDB']) {
          await expect(numbers.getByText(label, { exact: true })).toBeVisible()
        }
        await expect(numbers.getByText(`${stats.physicalCopies.toLocaleString('en-GB')} physical · ${stats.downloadCopies.toLocaleString('en-GB')} download`, { exact: true })).toBeVisible()
        await expect(numbers.getByText(`${stats.physicalAndDownloadCopies.toLocaleString('en-GB')} include both`, { exact: true })).toBeVisible()
        await expect(numbers.getByText("Distinct titles in your diary, including titles you don't own", { exact: true })).toBeVisible()
        await expect(numbers.getByText(/A match can still need checking/)).toBeVisible()
        await expect(numbers.locator('li', { hasText: "You've watched" })).toContainText(stats.watchedMovies.toLocaleString('en-GB'))
        await expect(numbers.locator('li', { hasText: 'Matched on TMDB' })).toContainText(stats.identifiedMovies.toLocaleString('en-GB'))
        expect(await section.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
        await section.screenshot({ path: testInfo.outputPath(`aa3-${person}-${theme}-${width}.png`) })
        await expect(section.getByRole('heading', { name: 'Formats (copies)', exact: true })).not.toBeVisible()
        await section.getByText('Collection breakdown', { exact: true }).click()
        for (const title of ['Formats (copies)', 'Where they live (copies)', 'Genres (titles)', 'Decades (titles)']) {
          await expect(section.getByRole('heading', { name: title, exact: true })).toBeVisible()
        }
        await expect(section.getByText('Copies can carry more than one format; these counts overlap.')).toBeVisible()
        const archive = section.getByRole('link', { name: 'Browse the archive', exact: true })
        await expect(archive).toHaveAttribute('href', '/movies')
        await page.setViewportSize({ width: 320, height: 844 })
        expect(await section.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
      }
    }
  })
}
