import { API_ORIGIN } from '../harness/env.ts'
import { expect, test } from '../support/test.ts'

test.describe('what Group X built', () => {
  test('Tell Craig: a line from Mark reaches Craig\'s Needs attention row, and only Craig can clear it', async ({ signedIn, api }) => {
    const mark = await signedIn('Mark')
    await mark.page.goto('/you')
    const line = `The Alien disc is in the Lounge, not the Garage (${Date.now()})`
    await mark.page.getByLabel(/Something wrong, or something you want/).fill(line)
    await mark.page.getByRole('button', { name: 'Send', exact: true }).click()
    await expect(mark.page.getByText('Sent to Craig.')).toBeVisible()

    const craig = await signedIn('Craig')
    await craig.page.goto('/dashboard')
    const row = craig.page.getByRole('region', { name: 'Needs attention' })
    await expect(row.getByText(line)).toBeVisible()

    // It is Craig's to read: Mark's own token is refused the list.
    const markApi = await api('Mark')
    await expect(markApi.get('/attention')).rejects.toThrow(/403/)

    await row.getByRole('listitem').filter({ hasText: line }).getByRole('button').first().click()
    await expect(row.getByText(line)).toHaveCount(0)
  })

  test('the Archive shows its first 60 films before the rest have arrived', async ({ signedIn }) => {
    const { page } = await signedIn('Craig')
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => (release = resolve))
    // The whole list is the slow request; hold it back, as a weak connection does.
    await page.route(
      (url) => url.origin === API_ORIGIN && url.pathname === '/api/v1/movies' && url.searchParams.get('perPage') === '2000',
      async (route) => {
        await gate
        await route.continue()
      },
    )
    await page.goto('/movies')
    const films = page.getByRole('main').getByRole('link', { name: /owned on/ })
    await expect(films.first()).toBeVisible()
    await expect(page.getByRole('status').filter({ hasText: /Showing the first 60 of \d+ films; loading the rest/ })).toBeVisible()
    release()
    await expect(page.getByText(/Showing the first 60/)).toHaveCount(0)
    await expect(page.getByRole('main').getByText(/^\d+ films$/)).toBeVisible()
  })
})
