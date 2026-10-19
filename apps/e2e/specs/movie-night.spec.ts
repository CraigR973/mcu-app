import { pushesTo, registerDevice } from '../support/push.ts'
import { expect, test } from '../support/test.ts'

test.describe('movie night', () => {
  test('Craig sends a night, the push opens it for Mark, they pick the same film and both see the match', async ({ signedIn, api }) => {
    const craigPhone = await registerDevice(await api('Craig'), 'craig-phone')
    const markPhone = await registerDevice(await api('Mark'), 'mark-phone')

    const craig = await signedIn('Craig')
    await craig.page.goto('/movie-night')
    await craig.page.getByRole('button', { name: 'Start movie night' }).click()
    await expect(craig.page).toHaveURL(/\/movie-night\/[0-9a-f-]{36}$/)
    const nightUrl = new URL(craig.page.url()).pathname
    await craig.page.getByRole('button', { name: 'Send to Mark' }).click()

    // What reached Mark's phone says which night to open.
    await expect.poll(() => pushesTo(markPhone).length, { message: 'a push to Mark' }).toBeGreaterThan(0)
    const [invite] = pushesTo(markPhone)
    expect(invite.title).toBe('Craig started a movie night')
    expect(invite.url).toBe(nightUrl)

    // Both look at the same shortlist; Craig picks the first film on it.
    const shortlist = craig.page.getByRole('region', { name: /Tonight's shortlist/ })
    const firstAdd = shortlist.getByRole('button', { name: /^Add / }).first()
    const film = (await firstAdd.innerText()).replace(/\s+/g, ' ').replace(/^Add\s*/, '').trim()
    await firstAdd.click()
    await expect(shortlist.getByText("You've added 1")).toBeVisible()

    // Mark opens the night the way the notification does: by its address.
    const mark = await signedIn('Mark')
    await mark.page.goto(invite.url as string)
    await expect(mark.page.getByRole('heading', { name: 'Movie night', level: 1 })).toBeVisible()
    await mark.page.getByRole('button', { name: `Add ${film}` }).click()
    await expect(mark.page.getByText("It's a match")).toBeVisible()

    // Craig is told by push.
    await expect.poll(() => pushesTo(craigPhone).map((p) => p.title).join('|')).toContain('match')

    // The match is stored on the night: a fresh page, with no live message, still shows it, for
    // either person, and the night names the film.
    await mark.page.reload()
    await expect(mark.page.getByText("It's a match")).toBeVisible()
    await expect(mark.page.getByText(film).first()).toBeVisible()
    await craig.page.reload()
    await expect(craig.page.getByText("It's a match")).toBeVisible()
    await expect(craig.page.getByText(film).first()).toBeVisible()
  })

  test("a page left open on the night is told of the match as it happens", async ({ signedIn, api }) => {
    await registerDevice(await api('Craig'), 'craig-phone')
    await registerDevice(await api('Mark'), 'mark-phone')

    const craig = await signedIn('Craig')
    await craig.page.goto('/movie-night')
    await craig.page.getByRole('button', { name: 'Start movie night' }).click()
    await expect(craig.page).toHaveURL(/\/movie-night\/[0-9a-f-]{36}$/)
    const nightUrl = new URL(craig.page.url()).pathname
    await craig.page.getByRole('button', { name: 'Send to Mark' }).click()
    const shortlist = craig.page.getByRole('region', { name: /Tonight's shortlist/ })
    const firstAdd = shortlist.getByRole('button', { name: /^Add / }).first()
    const film = (await firstAdd.innerText()).replace(/\s+/g, ' ').replace(/^Add\s*/, '').trim()
    await firstAdd.click()
    await expect(shortlist.getByText("You've added 1")).toBeVisible()

    const mark = await signedIn('Mark')
    await mark.page.goto(nightUrl)
    await mark.page.getByRole('button', { name: `Add ${film}` }).click()
    await expect(mark.page.getByText("It's a match")).toBeVisible()

    // Craig has not touched his page: the match arrives over the live stream.
    await expect(craig.page.getByText("It's a match")).toBeVisible()
  })
})
