import { expect, test } from '../support/test.ts'
import type { Person } from '../harness/env.ts'

type Counts = {
  totalMovies: number
  ownedWatchedMovies: number
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
  const added = await craig.post<{ id: string }>('/collection', {
    tmdbId: 1701,
    formats: ['4k_uhd', 'blu_ray', 'download'],
    section: 'Front', shelf: '2nd', hasPlaybackIssues: false,
  })
  try {
    for (const person of ['Craig', 'Mark'] as Person[]) {
      const after = await (await api(person)).get<Counts>('/collection/stats')
      expect(after.totalItems).toBe(before.totalItems + 1)
      expect(after.physicalCopies).toBe(before.physicalCopies + 1)
      expect(after.downloadCopies).toBe(before.downloadCopies + 1)
      expect(after.physicalAndDownloadCopies).toBe(before.physicalAndDownloadCopies + 1)
    }
  } finally {
    // The import journey pins 70 seeded titles; leave that invariant intact through the API.
    await craig.delete(`/collection/${added.id}`)
  }
})

for (const person of ['Craig', 'Mark'] as Person[]) {
  // AC2 (#337): one ledger. "Matched on TMDB" left Home; the formats are one stacked bar and
  // the breakdown no longer draws them a second time.
  test(`AA3 keeps the ledger's meanings and the breakdown reachable for ${person}`, async ({ signedIn, api }, testInfo) => {
    const { page, context } = await signedIn(person)
    const stats = await (await api(person)).get<Counts>('/collection/stats')
    const n = (value: number) => value.toLocaleString('en-GB')
    for (const theme of ['dark', 'light']) {
      await context.addInitScript((value) => localStorage.setItem('mcu-theme', value), theme)
      for (const width of [375, 1280]) {
        await page.setViewportSize({ width, height: 844 })
        await page.goto('/dashboard')
        const section = page.getByRole('region', { name: 'The collection', exact: true })
        const numbers = section.getByRole('list', { name: 'The collection in numbers' })
        for (const label of ['titles', 'Estimated used value', "You've watched", 'Formats at a glance']) {
          await expect(numbers.getByText(label, { exact: true })).toBeVisible()
        }
        await expect(numbers).toContainText(`${n(stats.totalItems)} copies · ${n(stats.physicalCopies)} on disc · ${n(stats.downloadCopies)} digital · ${n(stats.physicalAndDownloadCopies)} both`)
        await expect(numbers.getByText(`${n(stats.ownedWatchedMovies)} of ${n(stats.totalMovies)} titles you own`, { exact: true })).toBeVisible()
        await expect(page.getByText('Matched on TMDB')).toHaveCount(0)
        expect(await section.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
        await expect(section.getByRole('region', { name: 'Formats at a glance' })).toBeVisible()
        const archive = section.getByRole('link', { name: 'Browse the archive', exact: true })
        await expect(archive).toBeVisible()
        // Capture the whole component without the fixed bottom bar obscuring its last lines.
        // Functional checks use the normal 844px viewport before and after this capture.
        await page.setViewportSize({ width, height: 1200 })
        await section.screenshot({ path: testInfo.outputPath(`aa3-${person}-${theme}-${width}.png`) })
        await page.setViewportSize({ width, height: 844 })
        await expect(section.getByRole('heading', { name: 'Where they live (copies)', exact: true })).not.toBeVisible()
        await section.getByText('Collection breakdown', { exact: true }).click()
        for (const title of ['Where they live (copies)', 'Genres (titles)', 'Decades (titles)']) {
          await expect(section.getByRole('heading', { name: title, exact: true })).toBeVisible()
        }
        await expect(section.getByRole('heading', { name: 'Formats (copies)', exact: true })).toHaveCount(0)
        await expect(section.getByText('Copies can carry more than one format; these counts overlap.')).toHaveCount(1)
        await expect(archive).toHaveAttribute('href', '/movies')
        await page.setViewportSize({ width: 320, height: 844 })
        expect(await section.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
      }
    }
  })
}
