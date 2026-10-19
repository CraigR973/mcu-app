import { importSheet } from '../support/cli.ts'
import { expect, test } from '../support/test.ts'

test.describe('import', () => {
  test('the import CLI catalogues a sheet and the archive shows it, matched and unmatched alike', async ({ signedIn }) => {
    // The same CLI the owner runs on the spreadsheet, on the throwaway database, with TMDB faked.
    const result = importSheet('import-case', [
      ['Lantern Street', 'Blu-ray', 'Front 1st shelf'],
      ['Velvet Frontier', '4K', 'Back 2nd shelf'],
      ['Zzyzx Unheard-Of Feature', 'DVD', 'Garage'],
    ])
    expect(result.status, result.output).toBe(0)
    expect(result.output).toContain('Items inserted    : 3')

    const { page } = await signedIn('Craig')
    await page.goto('/movies')
    const archive = page.getByRole('main')
    // 70 seeded films and 3 imported; the first screen shows the first 60 of them.
    await expect(archive.getByText(/^73 films$/)).toBeVisible()

    for (const [typed, shown] of [
      ['Lantern Street', /Lantern Street/],
      ['Velvet Frontier', /Velvet Frontier/],
      // A title TMDB cannot match is still on the shelf; only its identification waits.
      ['Zzyzx', /Zzyzx Unheard-Of Feature/],
    ] as const) {
      await page.getByRole('combobox', { name: 'Search films' }).fill(typed)
      await page.getByRole('option', { name: shown }).first().click()
      await expect(page).toHaveURL(/\/movies\/[0-9a-f-]{36}$/)
      await expect(page.getByRole('heading', { name: shown }).first()).toBeVisible()
      await page.goto('/movies')
    }
  })

  test('the sheet\'s blank trailing row did not become a film', async ({ api }) => {
    const craig = await api('Craig')
    const page = await craig.get<{ items?: { title: string }[]; movies?: { title: string }[] }>('/movies?perPage=2000')
    const rows = page.items ?? page.movies ?? []
    expect(rows.every((row) => row.title.trim().length > 0)).toBe(true)
  })
})

test.describe('search', () => {
  test('the top bar finds an imported film and opens its page', async ({ signedIn }) => {
    const { page } = await signedIn('Craig')
    await page.goto('/dashboard')
    const box = page.getByRole('combobox', { name: 'Search films' })
    await box.fill('Quiet Engine')
    await page.getByRole('option', { name: /The Quiet Engine/ }).first().click()
    await expect(page).toHaveURL(/\/movies\/[0-9a-f-]{36}$/)
    await expect(page.getByRole('heading', { name: /The Quiet Engine/ }).first()).toBeVisible()
  })

  test('a film that is not owned is found on TMDB and opens its outside page', async ({ signedIn }) => {
    const { page } = await signedIn('Mark')
    await page.goto('/dashboard')
    await page.getByRole('combobox', { name: 'Search films' }).fill('Midnight Ferry')
    await page.getByRole('option', { name: /Midnight Ferry/ }).first().click()
    await expect(page).toHaveURL(/\/films\/tmdb\/1101$/)
    await expect(page.getByRole('heading', { name: /Midnight Ferry/ }).first()).toBeVisible()
  })
})
