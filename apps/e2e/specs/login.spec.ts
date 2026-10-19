import { expect, PINS, test } from '../support/test.ts'
import type { Person } from '../support/test.ts'
import type { Page } from '@playwright/test'

async function signInThroughTheForm(page: Page, person: Person, pin: string = PINS[person]) {
  await page.goto('/login')
  await page.getByLabel('Name').fill(person)
  await page.getByLabel('PIN', { exact: true }).fill(pin)
  await page.getByRole('button', { name: 'Enter the archive' }).click()
}

test.describe('login', () => {
  test('Craig signs in through the form and lands on Home', async ({ page }) => {
    await signInThroughTheForm(page, 'Craig')
    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(page.getByRole('main').getByRole('heading', { name: 'Home', level: 1 })).toBeVisible()
    // The administrator's navigation is there for Craig.
    await expect(page.getByRole('link', { name: 'Retailers' }).first()).toBeAttached()
  })

  test('Mark signs in, is walked through first-run once, and has no administrator screens', async ({ page, db }) => {
    // The seed marks both people as finished with first-run; put Mark back at the start.
    db.sql(`UPDATE profiles SET onboarding_completed_at_utc = NULL WHERE lower(display_name) = 'mark'`)

    await signInThroughTheForm(page, 'Mark')
    await expect(page).toHaveURL(/\/welcome$/)
    const enter = page.getByRole('button', { name: 'Enter the archive' })
    for (let step = 0; step < 8 && !(await enter.isVisible()); step += 1) {
      await page.getByRole('button', { name: 'Continue' }).click()
    }
    await enter.click()
    await expect(page).toHaveURL(/\/movies$/)

    // First-run does not come back.
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard$/)

    // Craig's screens turn Mark away.
    await page.goto('/retailers')
    await expect(page).toHaveURL(/\/unauthorized$/)
    await expect(page.getByRole('link', { name: 'Retailers' })).toHaveCount(0)
  })

  test('a wrong PIN is refused in words and does not sign anyone in', async ({ page }) => {
    await signInThroughTheForm(page, 'Mark', '1357')
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page).toHaveURL(/\/login$/)
    expect(await page.evaluate(() => localStorage.getItem('mcu.accessToken'))).toBeNull()
  })

  test('signing out leaves the sign-in form, and the archive is closed behind it', async ({ page }) => {
    await signInThroughTheForm(page, 'Craig')
    await expect(page).toHaveURL(/\/dashboard$/)
    await page.goto('/you')
    await page.getByRole('main').getByRole('button', { name: 'Sign out' }).click()
    await expect(page).toHaveURL(/\/login/)
    await page.goto('/movies')
    await expect(page).toHaveURL(/\/login/)
  })
})
