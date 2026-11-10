import { randomUUID } from 'node:crypto'

import { expect, test } from '../support/test.ts'

interface Copy {
  id: string
  movieId: string
}

// AE2 (#355, points 1, 2, 15 and 17): Home's Highlights opens on Recently added; the featured
// film's buttons share one row under its poster and title; the estimate's method opens the width
// of the card. For both people, at 375 px, in both themes.
for (const person of ['Craig', 'Mark'] as const) {
  test(`AE2 Home opens on Recently added, keeps the featured buttons on one row, and opens the estimate full width, for ${person}`, async ({ signedIn, api }, testInfo) => {
    const mark = await api('Mark'), craig = await api('Craig')
    const title = `AE2 added ${randomUUID().slice(0, 8)}`
    // Mark adds a 4K in the app: the newest addition there is.
    const copy = await mark.post<Copy>('/collection', {
      title,
      formats: ['4k_uhd'],
      section: 'Garage',
      hasPlaybackIssues: false,
      clientRequestId: randomUUID(),
    })
    try {
      const { page, context } = await signedIn(person)
      // A stored estimate, as AB2 fixes one, so its method is there to open.
      await page.route('**/api/v1/collection/value', async (route) => {
        const response = await route.fetch()
        await route.fulfill({ response, json: { ...(await response.json()), total: '12345.67', discs: 5678, pricedDiscs: 1234, salesBackedDiscs: 12 } })
      })
      for (const theme of ['light', 'dark'] as const) {
        await context.addInitScript((value) => localStorage.setItem('mcu-theme', value), theme)
        await page.setViewportSize({ width: 375, height: 812 })
        await page.goto('/dashboard')
        const main = page.getByRole('main')

        // Recently added: the first tab, open on arrival, the new copy first, who, when and what.
        const tabs = main.getByRole('tablist', { name: 'Highlights' }).getByRole('tab')
        await expect(tabs.first()).toHaveText('Recently added')
        await expect(tabs.first()).toHaveAttribute('aria-selected', 'true')
        const newest = main.getByRole('tabpanel').getByRole('link').first()
        await expect(newest).toHaveAttribute('href', `/movies/${copy.movieId}`)
        await expect(newest).toContainText(title)
        await expect(newest).toContainText(/Mark · \d{1,2} [A-Z][a-z]{2} · 4K UHD/)

        // The featured film: deal once so all three buttons show, then they share one row.
        const featured = page.locator('section[aria-labelledby="home-featured-title"]')
        const lucky = featured.getByRole('group', { name: 'Feeling lucky' })
        await lucky.getByRole('button', { name: /^Deal (a film|another)$/ }).click()
        const open = lucky.getByRole('link', { name: 'Open the film' })
        const deal = lucky.getByRole('button', { name: 'Deal another' })
        const again = lucky.getByRole('button', { name: 'Start again' })
        await expect(open).toBeVisible()
        await expect(again).toBeVisible()
        // One layout snapshot of the row, whole pixels: three separate reads could each catch the
        // page mid-shift while rows above it are still arriving (WebKit did, on CI).
        const tops = await deal.evaluate((button) =>
          Array.from(button.parentElement?.children ?? []).map((control) => Math.round(control.getBoundingClientRect().top)),
        )
        expect(tops, 'Open the film, Deal another and Start again').toHaveLength(3)
        expect(new Set(tops).size, 'the buttons share one row').toBe(1)
        for (const control of [open, deal]) {
          expect(await control.evaluate((element) => element.scrollWidth <= element.clientWidth), 'a label fits its button').toBe(true)
        }
        // Poster and title open the film too.
        const href = await open.getAttribute('href')
        await expect(featured.getByRole('heading', { level: 2 }).getByRole('link')).toHaveAttribute('href', href ?? '')
        await featured.scrollIntoViewIfNeeded()
        await featured.screenshot({ path: testInfo.outputPath(`ae2-featured-${person}-${theme}-375.png`) })

        // How this estimate works: the width of the card, under both figures.
        const numbers = main.getByRole('list', { name: 'The collection in numbers' })
        await numbers.getByText('How this estimate works', { exact: true }).click()
        const method = numbers.locator('details').filter({ hasText: 'How this estimate works' })
        await expect(method.getByText(/At least three observed sales/)).toBeVisible()
        const figures = await numbers.locator('.grid').first().boundingBox()
        const panel = await method.boundingBox()
        expect(panel && figures && panel.width >= figures.width - 1, 'the method spans both figures').toBe(true)
        await numbers.scrollIntoViewIfNeeded()
        await numbers.screenshot({ path: testInfo.outputPath(`ae2-estimate-${person}-${theme}-375.png`) })

        expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), '375 px fits').toBe(true)
      }
    } finally {
      await craig.delete(`/collection/${copy.id}`)
    }
  })
}
