import type { Page } from '@playwright/test'
import { probe } from '../support/probe.ts'
import { expect, test } from '../support/test.ts'

const BARCODE = '5051429700106' // printed on Midnight Ferry in the fake eBay

async function lookUp(page: Page, barcode: string) {
  await page.goto('/collection/add')
  await page.getByRole('tab', { name: /Scan barcode/ }).click()
  // The typed digits take the same road a camera hit does (the camera itself is a real-device
  // check: OWNER-ACTIONS 1d).
  await page.getByLabel('Or type the digits').fill(barcode)
  await page.getByRole('button', { name: 'Look up' }).click()
}

test.describe('add via scan', () => {
  test('a barcode finds the film on eBay and TMDB, the person confirms it, and the disc is added', async ({ signedIn }) => {
    const { page } = await signedIn('Craig')
    await lookUp(page, BARCODE)

    // Nothing is added until the person has looked at the film and said so.
    await expect(page.getByText('Is this the film on the case?')).toBeVisible()
    await expect(page.getByText('Midnight Ferry', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'This is the disc' }).click()

    await page.getByRole('combobox', { name: 'Section' }).selectOption({ label: 'Garage' })
    await page.getByRole('textbox', { name: 'Location' }).fill('Garage top shelf')
    await page.getByRole('button', { name: 'Add “Midnight Ferry”' }).click()

    const film = page.getByRole('main')
    await expect(film.getByRole('heading', { name: 'Midnight Ferry', level: 1 })).toBeVisible()
    await expect(film.getByText('1 owned copy')).toBeVisible()
    await expect(film.getByText('Garage top shelf')).toBeVisible()
  })

  test('a barcode already on a copy says so, naming the film, instead of adding a second', async ({ signedIn, api }) => {
    const salted = '5022222333341'
    const craig = await api('Craig')
    await craig.post('/collection', {
      tmdbId: 1202,
      barcode: salted,
      formats: ['blu_ray'],
      section: 'Front',
      shelf: '1st shelf',
      hasPlaybackIssues: false,
    })

    const { page } = await signedIn('Mark')
    await lookUp(page, salted)
    await probe(page, 'scan-again')
    await expect(page.getByText(/already/i).first()).toBeVisible()
    await expect(page.getByText('The Salt Road').first()).toBeVisible()
  })
})
