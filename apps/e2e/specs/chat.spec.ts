import type { Page } from '@playwright/test'
import { expect, test } from '../support/test.ts'
import { world } from '../support/world.ts'

async function ask(page: Page, text: string) {
  await page.getByRole('textbox', { name: 'Message to the assistant' }).fill(text)
  await page.getByRole('button', { name: 'Send message' }).click()
}

test.describe('chat session', () => {
  test('two messages in one conversation: the second carries the first answer and is answered', async ({ signedIn }) => {
    const { page } = await signedIn('Mark')
    await page.goto('/assistant')
    await ask(page, 'Which of my films are westerns?')
    const log = page.getByRole('log')
    await expect(log.getByText(/You asked: Which of my films are westerns\?\. This answer is recorded\./)).toBeVisible()

    await ask(page, 'And anything older than 1980?')
    await expect(log.getByText(/You asked: And anything older than 1980\?\. This answer is recorded\./)).toBeVisible()

    // The second request sent the first question and its answer back. A block the API would not
    // accept (X7's `parsed_output`) is a 400 from the fake, so an answer here means it was sent right.
    const second = world.log().filter((c) => c.kind === 'model' && String(c.lastUser).includes('older than 1980')).at(-1)
    expect(second?.roles).toEqual(['user', 'assistant', 'user'])
    expect(second?.blocks).toEqual([['text'], ['text'], ['text']])
    await expect(page.getByText("The assistant isn't working right now")).toHaveCount(0)
  })

  test('a write waits behind a Yes/No card, the box stays shut meanwhile, and Yes writes it once', async ({ signedIn, api }) => {
    world.setScenario({
      anthropic: {
        rules: [
          {
            lastUserContains: 'i watched the quiet engine',
            toolUse: { name: 'log_watch', input: { title: 'The Quiet Engine', rating: 4 } },
          },
          { lastIsToolResult: true, text: 'Logged. Anything else?' },
        ],
      },
    })
    const { page } = await signedIn('Mark')
    await page.goto('/assistant')
    // Start the conversation and let its (empty) record arrive before asking. A first message in a
    // brand-new conversation races that record against the card: a slow link can wipe the card
    // the stream has just raised (recorded in DECISIONS.md #285, not part of this case).
    const record = page.waitForResponse(
      (r) => /\/ai\/conversations\/[0-9a-f-]{36}$/.test(r.url()) && r.request().method() === 'GET',
    )
    await page.getByRole('button', { name: 'New chat' }).click()
    await record
    await ask(page, 'I watched The Quiet Engine and give it 4 stars')

    const card = page.getByText('Can I do this?')
    await expect(card).toBeVisible()
    // Nothing has been written, and the box is locked until the card is answered.
    const box = page.getByRole('textbox', { name: 'Message to the assistant' })
    await expect(box, `placeholder: ${await box.getAttribute('placeholder')}`).toBeDisabled()
    const mark = await api('Mark')
    const before = await mark.get<{ items: unknown[] }>('/watch-log')
    await page.getByRole('button', { name: 'Yes, do it' }).click()

    await expect(page.getByText('Logged. Anything else?')).toBeVisible()
    await expect(card).toHaveCount(0)
    await expect(box).toBeEnabled()
    const after = await mark.get<{ items: unknown[] }>('/watch-log')
    expect(after.items.length).toBe(before.items.length + 1)
    // The model was asked twice: the question, then the question with its tool call and result.
    const turns = world.log().filter((c) => c.kind === 'model')
    expect((turns.at(-1)?.blocks as string[][]).flat()).toContain('tool_result')
  })

  test('the daily cap stops a message with the app\'s own words', async ({ signedIn, api }) => {
    const craig = await api('Craig')
    const usage = await craig.get<{ messageCap: number; messagesRemaining: number }>('/ai/usage')
    const used = usage.messageCap - usage.messagesRemaining
    await craig.put('/ai/settings', { dailyMessageCap: used + 1 })

    const { page } = await signedIn('Craig')
    await page.goto('/assistant')
    await expect(page.getByText(/1 of \d+ left today/)).toBeVisible()
    await ask(page, 'One message left')
    await expect(page.getByText(/You asked: One message left/)).toBeVisible()
    await ask(page, 'And one more')
    await expect(page.getByRole('alert')).toContainText("You have used all 1 of today's messages.")
    await craig.put('/ai/settings', { dailyMessageCap: 50 })
  })

  test('the dictation button is there where the browser can listen, and the skip is on record where it cannot', async ({ signedIn, browserName }) => {
    const { page } = await signedIn('Mark')
    await page.goto('/assistant')
    // Batch 32 hides the button rather than show it dead. A silent skip is how the derived-field
    // tests once hid: this one says so in the report, and says why.
    test.skip(browserName === 'firefox', 'Firefox has no Web Speech API, so the dictation button is hidden there by design (Batch 32)')
    await expect(page.getByRole('button', { name: 'Dictate a question' })).toBeVisible()
  })
})
