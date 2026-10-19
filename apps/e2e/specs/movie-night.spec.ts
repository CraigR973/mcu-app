import { API_ORIGIN } from '../harness/env.ts'
import { pushesTo, registerDevice } from '../support/push.ts'
import { expect, test } from '../support/test.ts'

test.describe('movie night', () => {
  test('Craig sends a night, the push opens it for Mark, they pick the same film and both see the match', async ({ signedIn, api }) => {
    const craigApi = await api('Craig')
    const markApi = await api('Mark')
    const craigPhone = await registerDevice(craigApi, 'craig-phone')
    const markPhone = await registerDevice(markApi, 'mark-phone')

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

    // Mark opens the night the way the notification does: by its address.
    const mark = await signedIn('Mark')
    await mark.page.goto(invite.url as string)
    await expect(mark.page.getByRole('heading', { name: 'Movie night', level: 1 })).toBeVisible()
    await mark.page.getByRole('button', { name: `Add ${film}` }).click()
    await expect(mark.page.getByText("It's a match")).toBeVisible()

    // Craig is told live, and by push.
    const said: string[] = []
    craig.page.on('console', (message) => said.push(message.text().slice(0, 160)))
    // A page that is not in front may be throttled by the engine (WebKit pauses a background
    // page's streams); a person watching the night has it in front.
    await craig.page.bringToFront()
    const shownLive = craig.page.getByText("It's a match")
    const told = await shownLive.waitFor({ timeout: 10_000 }).then(() => true, () => false)
    if (!told) {
      // Say what this browser does with a streamed answer, for the failure message.
      const stream = await craig.page.evaluate(
        async ({ api, id }) => {
          const token = localStorage.getItem('mcu.accessToken') ?? ''
          const started = Date.now()
          const response = await fetch(`${api}/api/v1/movie-night/${id}/events`, {
            headers: { authorization: `Bearer ${token}` },
          })
          const reader = response.body!.getReader()
          const first = await Promise.race([
            reader.read().then((r) => `first chunk ${r.value?.length ?? 0} bytes after ${Date.now() - started} ms`),
            new Promise<string>((resolve) => setTimeout(() => resolve('no chunk in 5 s'), 5000)),
          ])
          void reader.cancel()
          return first
        },
        { api: API_ORIGIN, id: nightUrl.split('/').pop() ?? '' },
      )
      throw new Error(`Craig's page was not told live. Console: ${said.join(' | ')}. Stream: ${stream}`)
    }
    await expect.poll(() => pushesTo(craigPhone).map((p) => p.title).join('|')).toContain('match')

    // The match is stored on the night: a fresh page, with no live message, still shows it.
    await mark.page.reload()
    await expect(mark.page.getByText("It's a match")).toBeVisible()
    await expect(mark.page.getByText(film).first()).toBeVisible()
  })
})
