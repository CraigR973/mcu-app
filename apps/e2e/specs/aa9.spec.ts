import { expect, test } from '../support/test.ts'
import { world } from '../support/world.ts'

for (const person of ['Craig', 'Mark'] as const) {
  test(`AA9 gives ${person} a usable first screen, role guidance and a reachable composer`, async ({ signedIn, api }, testInfo) => {
    const modelCallsBefore = world.log().filter(call => call.kind === 'model').length
    const client = await api(person)
    const before = await client.get<{ total: number }>('/ai/conversations')
    const { page, context } = await signedIn(person)
    for (const theme of ['dark', 'light']) {
      await context.addInitScript(value => localStorage.setItem('mcu-theme', value), theme)
      for (const size of [{ width: 375, height: 844 }, { width: 320, height: 640 }, { width: 375, height: 500 }, { width: 1280, height: 844 }]) {
        await page.setViewportSize(size)
        await page.goto('/assistant')
        await expect(page.getByRole('heading', { name: 'Ask about your collection' })).toBeVisible()
        await expect(page.getByRole('heading', { name: 'Assistant', exact: true })).toHaveCount(1)
        await expect(page.getByText(/AI calls: \d+ of \d+ left today/)).toBeVisible()
        await expect(page.getByText(person === 'Craig' ? /You can also add to the shared wanted list/ : /You can read the shared wanted list/)).toBeVisible()
        if (person === 'Mark') await expect(page.getByText(/You can also add/)).toHaveCount(0)
        await page.getByRole('button', { name: 'Unwatched 4Ks', exact: true }).click()
        const draft = page.getByRole('textbox', { name: 'Message to the assistant' })
        await expect(draft).toHaveValue('Which 4Ks have I not watched?')
        await draft.press('End')
        await draft.press('Enter')
        await draft.press('T')
        await expect(draft).toHaveValue('Which 4Ks have I not watched?\nT')
        await expect(page.getByRole('button', { name: 'Send message' })).toBeEnabled()
        const region = page.getByRole('region', { name: 'Assistant page', exact: true })
        expect(await region.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true)
        const button = await page.getByRole('button', { name: 'Send message' }).boundingBox()
        expect(button).not.toBeNull()
        expect(button!.y).toBeGreaterThanOrEqual(0)
        expect(button!.y + button!.height).toBeLessThanOrEqual(size.height)
        if (size.width < 1024) {
          const nav = await page.getByRole('navigation', { name: 'Primary mobile navigation' }).boundingBox()
          expect(nav).not.toBeNull()
          expect(button!.y + button!.height).toBeLessThanOrEqual(nav!.y)
          await page.getByRole('button', { name: 'Recent chats', exact: true }).click()
          await expect(page.getByRole('heading', { name: 'Recent chats', exact: true })).toBeVisible()
          await page.getByRole('button', { name: 'Back to conversation' }).click()
          await expect(draft).toHaveValue('Which 4Ks have I not watched?\nT')
        }
        if (size.width === 375 && size.height === 844) await page.screenshot({ path: testInfo.outputPath(`aa9-${person}-${theme}-375.png`) })
      }
    }
    expect((await client.get<{ total: number }>('/ai/conversations')).total).toBe(before.total)
    expect(world.log().filter(call => call.kind === 'model')).toHaveLength(modelCallsBefore)
  })
}

test('AA9 reloads an interrupted answer instead of sending its already-saved question twice', async ({ signedIn, api }, testInfo) => {
  const { page } = await signedIn('Mark')
  await page.setViewportSize({ width: 375, height: 500 })
  let messages = 0
  await page.route(/\/ai\/conversations\/[0-9a-f-]+\/messages$/, async route => {
    messages += 1
    const response = await route.fetch()
    // The real server commits its answer; only its terminal frame is lost on the way back.
    const frames = (await response.text()).split('\n\n').filter(frame => frame.trim()).filter(frame => JSON.parse(frame.replace(/^data:\s*/, '')).kind !== 'done')
    await route.fulfill({ response, body: frames.join('\n\n') + '\n\n' })
  })
  await page.goto('/assistant')
  const draft = page.getByRole('textbox', { name: 'Message to the assistant' })
  await draft.fill('AA9 keep this interrupted question')
  await expect(page.getByRole('button', { name: 'Send message' })).toBeEnabled()
  await page.getByRole('button', { name: 'Send message' }).click()
  await expect(page.getByRole('alert')).toContainText('ended before it was complete')
  const id = new URL(page.url()).searchParams.get('c')
  expect(id).toBeTruthy()
  try {
    await expect(draft).toHaveValue('AA9 keep this interrupted question')
    await expect(page.getByRole('button', { name: 'Send message' })).toBeDisabled()
    await page.getByRole('button', { name: 'Reload conversation' }).click()
    await expect(page.getByText(/Your question is already saved/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Send message' })).toBeDisabled()
    await expect(page.getByRole('log').getByText('AA9 keep this interrupted question', { exact: true })).toHaveCount(1)
    const send = await page.getByRole('button', { name: 'Send message' }).boundingBox()
    const nav = await page.getByRole('navigation', { name: 'Primary mobile navigation' }).boundingBox()
    expect(send).not.toBeNull()
    expect(nav).not.toBeNull()
    expect(send!.y + send!.height).toBeLessThanOrEqual(nav!.y)
    await page.screenshot({ path: testInfo.outputPath('aa9-recovered-short-375.png') })
    await page.setViewportSize({ width: 375, height: 844 })
    await expect(page.getByText(/Your question is already saved/)).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath('aa9-recovered-saved-question.png') })
    await page.getByRole('button', { name: 'Start a different question' }).click()
    await expect(draft).toHaveValue('')
    expect(messages).toBe(1)
  } finally { if (id) await (await api('Mark')).delete(`/ai/conversations/${id}`) }
})

test('AA9 binds an in-flight answer to its chat when browser Back changes the selected conversation', async ({ signedIn, api }) => {
  const { page } = await signedIn('Mark')
  await page.setViewportSize({ width: 375, height: 844 })
  let release!: () => void
  const allowed = new Promise<void>(resolve => { release = resolve })
  let held!: () => void
  const received = new Promise<void>(resolve => { held = resolve })
  await page.route(/\/ai\/conversations\/[0-9a-f-]+\/messages$/, async route => {
    const response = await route.fetch()
    held()
    await allowed
    await route.fulfill({ response })
  })
  await page.goto('/assistant')
  await page.getByRole('textbox', { name: 'Message to the assistant' }).fill('AA9 answer belongs to its origin')
  await expect(page.getByRole('button', { name: 'Send message' })).toBeEnabled()
  await page.getByRole('button', { name: 'Send message' }).click()
  await received
  const id = new URL(page.url()).searchParams.get('c')
  expect(id).toBeTruthy()
  try {
    await expect(page.getByRole('button', { name: 'New chat', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Recent chats', exact: true })).toBeDisabled()
    await page.goBack()
    await expect(page).toHaveURL(/\/assistant$/)
    release()
    await expect(page.getByRole('button', { name: 'Send message' })).toBeVisible()
    await expect(page.getByRole('log').getByText(/You asked: AA9 answer belongs/)).toHaveCount(0)
    const saved = await (await api('Mark')).get<{ messages: { text: string }[] }>(`/ai/conversations/${id}`)
    expect(saved.messages.some(turn => turn.text.includes('You asked: AA9 answer belongs'))).toBe(true)
  } finally { release(); if (id) await (await api('Mark')).delete(`/ai/conversations/${id}`) }
})

test('AA9 confirms deletion of a named chat and keeps a viewing already confirmed in it', async ({ signedIn, api }, testInfo) => {
  world.setScenario({ anthropic: { rules: [
    { lastUserContains: 'i watched the quiet engine', toolUse: { name: 'log_watch', input: { title: 'The Quiet Engine', rating: 4 } } },
    { lastIsToolResult: true, text: 'Viewing recorded.' },
  ] } })
  const client = await api('Mark')
  const before = await client.get<{ items: { id: string }[] }>('/watch-log')
  const { page } = await signedIn('Mark')
  await page.setViewportSize({ width: 375, height: 844 })
  let id: string | null = null
  let created: { id: string }[] = []
  try {
    await page.goto('/assistant')
    await page.getByRole('textbox', { name: 'Message to the assistant' }).fill('I watched The Quiet Engine and give it 4 stars')
    await expect(page.getByRole('button', { name: 'Send message' })).toBeEnabled()
    await page.getByRole('button', { name: 'Send message' }).click()
    await expect(page.getByText('Can I do this?')).toBeVisible()
    id = new URL(page.url()).searchParams.get('c')
    await expect(page.getByText(/The Quiet Engine \(2011\)/)).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Message to the assistant' })).toBeDisabled()
    expect((await client.get<{ items: { id: string }[] }>('/watch-log')).items.length).toBe(before.items.length)
    await page.getByRole('button', { name: 'Yes, do it' }).click()
    await expect(page.getByText('Viewing recorded.')).toBeVisible()
    id = new URL(page.url()).searchParams.get('c')
    const after = await client.get<{ items: { id: string }[] }>('/watch-log')
    created = after.items.filter(item => !before.items.some(previous => previous.id === item.id))
    expect(created).toHaveLength(1)
    await page.getByRole('button', { name: 'Delete this conversation' }).click()
    const dialog = page.getByRole('dialog', { name: 'Delete conversation' })
    await expect(dialog.getByText('I watched The Quiet Engine and give it 4 stars', { exact: true })).toBeVisible()
    await expect(dialog.getByText(/Viewings and Wanted additions you already confirmed stay recorded/)).toBeVisible()
    expect((await client.get<{ items: { id: string }[] }>('/ai/conversations')).items.some(item => item.id === id)).toBe(true)
    await page.screenshot({ path: testInfo.outputPath('aa9-delete-confirmation.png') })
    await dialog.getByRole('button', { name: 'Keep chat' }).click()
    await expect(dialog).toHaveCount(0)
    await page.getByRole('button', { name: 'Delete this conversation' }).click()
    await page.getByRole('button', { name: 'Delete chat', exact: true }).click()
    await expect(dialog).toHaveCount(0)
    expect((await client.get<{ items: { id: string }[] }>('/ai/conversations')).items.some(item => item.id === id)).toBe(false)
    expect((await client.get<{ items: { id: string }[] }>('/watch-log')).items.some(item => item.id === created[0].id)).toBe(true)
    id = null
  } finally {
    // Discover any write even if a later UI assertion failed before the normal read-back.
    const remaining = await client.get<{ items: { id: string }[] }>('/watch-log')
    for (const item of remaining.items.filter(item => !before.items.some(previous => previous.id === item.id))) await client.delete(`/watch-log/${item.id}`)
    if (id) await client.delete(`/ai/conversations/${id}`)
  }
})

test('AA9 keeps a draft when the configured status is unavailable', async ({ signedIn }) => {
  const modelCallsBefore = world.log().filter(call => call.kind === 'model').length
  const { page } = await signedIn('Mark')
  await page.route('**/api/v1/ai/status', route => route.fulfill({ json: { configured: false, model: 'fixture' } }))
  await page.goto('/assistant')
  await expect(page.getByRole('alert')).toContainText('assistant is unavailable')
  const draft = page.getByRole('textbox', { name: 'Message to the assistant' })
  await draft.fill('Keep this draft until the assistant is ready')
  await expect(page.getByRole('button', { name: 'Send message' })).toBeDisabled()
  await expect(draft).toHaveValue('Keep this draft until the assistant is ready')
  expect(world.log().filter(call => call.kind === 'model')).toHaveLength(modelCallsBefore)
})
