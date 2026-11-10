import type { Locator, Page } from '@playwright/test'
import { expect } from './test.ts'

/** AE5 (#355, point 13): At the cinema folds its listings and its events until opened. Opens
 *  one and returns its region. */
export async function unfold(page: Page, name: 'Not matched to a film yet' | 'Events and double bills'): Promise<Locator> {
  const region = page.getByRole('region', { name, exact: true })
  const details = region.locator('details')
  await expect(details).toHaveCount(1)
  if (!(await details.evaluate((element) => (element as HTMLDetailsElement).open))) await region.locator('summary').click()
  await expect(details).toHaveAttribute('open', '')
  return region
}

/** A film's own link on its day card (AE5), past the time chips that book. */
export const filmLink = (card: Locator, title: string): Locator => card.getByRole('link', { name: title, exact: true })

/** Posters from the fake world are not images; draw each as a tinted card, so a screenshot
 *  reads as the phone would. */
export async function posters(page: Page): Promise<void> {
  await page.route('https://image.tmdb.org/t/p/**', async route => {
    const name = new URL(route.request().url()).pathname.split('/').pop() ?? ''
    const hue = [...name].reduce((sum, c) => sum + c.charCodeAt(0), 0) % 360
    await route.fulfill({
      contentType: 'image/svg+xml',
      body: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 300"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="hsl(${hue} 45% 38%)"/><stop offset="1" stop-color="hsl(${(hue + 40) % 360} 50% 16%)"/></linearGradient></defs><rect width="200" height="300" fill="url(#g)"/><text x="100" y="250" fill="white" font-family="Georgia" font-size="22" text-anchor="middle">${name.replace(/^a[ce]\d-|\.jpg$/g, '')}</text></svg>`,
    })
  })
}
