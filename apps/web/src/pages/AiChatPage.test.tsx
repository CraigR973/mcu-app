// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AiChatPage from './AiChatPage'

const mocks = vi.hoisted(() => ({
  role: 'viewer' as 'viewer' | 'admin',
  createAiConversation: vi.fn(),
  deleteAiConversation: vi.fn(),
  fetchAiConversation: vi.fn(),
  fetchAiConversations: vi.fn(),
  fetchAiStatus: vi.fn(),
  fetchAiUsage: vi.fn(),
  resolveAiToolCall: vi.fn(),
  streamAiMessage: vi.fn(),
}))

vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { role: mocks.role, displayName: mocks.role === 'admin' ? 'Craig' : 'Mark' } }) }))

vi.mock('@/components/MicButton', () => ({
  MicButton: () => null,
}))

vi.mock('@/lib/api', () => ({
  ...mocks,
  describeToolCall: () => 'Record a collection change.',
}))

const CONVERSATION_ID = '3f2504e0-4f89-41d3-9a0c-0305e82c3301'
const CREATED_ID = '3f2504e0-4f89-41d3-9a0c-0305e82c3302'

async function* answerWith(text: string) {
  yield { kind: 'text' as const, text }
  yield { kind: 'done' as const, text: '' }
}

async function* emptyStream() {
  yield { kind: 'done' as const, text: '' }
}

function NavigationProbe() {
  const navigate = useNavigate()
  return <button onClick={() => navigate('/assistant?c=3f2504e0-4f89-41d3-9a0c-0305e82c3309')}>Browser history to another chat</button>
}

function renderPage(path = `/assistant?c=${CONVERSATION_ID}`) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <NavigationProbe /><AiChatPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mocks.role = 'viewer'
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  Object.defineProperty(Element.prototype, 'scrollIntoView', {
    configurable: true,
    value: vi.fn(),
  })
  mocks.createAiConversation.mockReset().mockResolvedValue({
    id: CREATED_ID,
    title: 'New conversation',
    createdAt: '2026-09-10T12:00:00Z',
    updatedAt: '2026-09-10T12:00:00Z',
  })
  mocks.deleteAiConversation.mockReset().mockResolvedValue(undefined)
  mocks.fetchAiStatus.mockReset().mockResolvedValue({ configured: true, model: 'test-model' })
  mocks.fetchAiUsage.mockReset().mockResolvedValue({
    messages: 1,
    messageCap: 20,
    messagesRemaining: 19,
    costUsd: '0.01',
    costCapUsd: '1.00',
    blocked: false,
    limitMessage: null,
    resetsAt: '2026-09-11T00:00:00Z',
  })
  mocks.fetchAiConversations.mockReset().mockResolvedValue({
    items: [{
      id: CONVERSATION_ID,
      title: 'Archive questions',
      createdAt: '2026-09-10T10:00:00Z',
      updatedAt: '2026-09-10T11:00:00Z',
    }],
    total: 1,
  })
  mocks.fetchAiConversation.mockReset().mockResolvedValue({
    id: CONVERSATION_ID,
    title: 'Archive questions',
    createdAt: '2026-09-10T10:00:00Z',
    updatedAt: '2026-09-10T11:00:00Z',
    messages: [
      {
        id: '3f2504e0-4f89-41d3-9a0c-0305e82c3310',
        role: 'user',
        text: 'Where is Jaws?',
        sequence: 1,
        createdAt: '2026-09-10T10:00:00Z',
      },
      {
        id: '3f2504e0-4f89-41d3-9a0c-0305e82c3311',
        role: 'assistant',
        text: 'Jaws is on shelf B4.',
        sequence: 2,
        createdAt: '2026-09-10T10:00:01Z',
      },
    ],
    pendingToolCalls: [],
  })
  mocks.streamAiMessage.mockReset().mockImplementation(() => answerWith('Alien is on shelf C2.'))
  mocks.resolveAiToolCall.mockReset().mockImplementation(() => emptyStream())
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('AiChatPage', () => {
  it('keeps stored history during a live turn and exposes mobile conversation controls', async () => {
    renderPage()

    expect(await screen.findByText('Jaws is on shelf B4.')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Recent chats' })).not.toBeNull()
    expect(screen.getByRole('button', { name: 'New chat' })).not.toBeNull()

    fireEvent.change(screen.getByLabelText('Message to the assistant'), {
      target: { value: 'Where is Alien?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('Alien is on shelf C2.')).not.toBeNull()
    expect(screen.getByText('Jaws is on shelf B4.')).not.toBeNull()
    expect(screen.getByText('Where is Alien?')).not.toBeNull()
    expect(mocks.streamAiMessage).toHaveBeenCalledWith(CONVERSATION_ID, 'Where is Alien?')
  })

  it('renders a conversation creation failure and leaves the question available to retry', async () => {
    mocks.createAiConversation.mockRejectedValueOnce(new Error('Conversation service unavailable.'))
    renderPage('/assistant')

    await vi.waitFor(() => expect(screen.queryByText('Checking assistant availability…')).toBeNull())
    const input = screen.getByLabelText('Message to the assistant') as HTMLTextAreaElement
    fireEvent.change(input, { target: { value: 'What should we watch?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('Conversation service unavailable.')).not.toBeNull()
    expect(input.value).toBe('What should we watch?')
    expect(mocks.streamAiMessage).not.toHaveBeenCalled()
  })

  it('catches and renders a stream failure without discarding the transcript', async () => {
    mocks.streamAiMessage.mockImplementationOnce(() => (async function* failedStream() {
      yield await Promise.reject(new Error('The live response disconnected.'))
    })())
    renderPage()

    expect(await screen.findByText('Jaws is on shelf B4.')).not.toBeNull()
    fireEvent.change(screen.getByLabelText('Message to the assistant'), {
      target: { value: 'Recommend one.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('The live response disconnected.')).not.toBeNull()
    expect(screen.getByText('Jaws is on shelf B4.')).not.toBeNull()
    expect(within(screen.getByRole('log')).getByText('Recommend one.')).not.toBeNull()
    expect((screen.getByLabelText('Message to the assistant') as HTMLTextAreaElement).value).toBe('Recommend one.')
  })

  it('locks the message box while a card waits, and unlocks it once the card is answered', async () => {
    // Batch X7 (AI45-02): typing instead of tapping broke the conversation for good.
    const waiting = {
      id: CONVERSATION_ID,
      title: 'Archive questions',
      createdAt: '2026-09-10T10:00:00Z',
      updatedAt: '2026-09-10T11:00:00Z',
      messages: [],
      pendingToolCalls: [
        {
          id: '3f2504e0-4f89-41d3-9a0c-0305e82c3320',
          toolName: 'log_watch',
          input: { title: 'Heat' },
        },
      ],
    }
    // Once answered, the server holds no card: it settles the call before it streams the reply.
    mocks.fetchAiConversation
      .mockResolvedValueOnce(waiting)
      .mockResolvedValue({ ...waiting, pendingToolCalls: [] })
    renderPage()

    expect(await screen.findByText('Can I do this?')).not.toBeNull()
    const input = screen.getByLabelText('Message to the assistant') as HTMLTextAreaElement
    expect(input.disabled).toBe(true)
    expect(input.placeholder).toBe('Answer the card above first')

    fireEvent.click(screen.getByRole('button', { name: /Yes, do it/ }))

    expect(mocks.resolveAiToolCall).toHaveBeenCalledWith('3f2504e0-4f89-41d3-9a0c-0305e82c3320', true)
    await vi.waitFor(() => expect(input.disabled).toBe(false))
  })

  // Batch Z1 (`DECISIONS.md` #287). A first message in a new conversation opens the
  // conversation, and that record is asked for before the server holds any card. On a slow
  // link it arrived after the stream had raised the card, and wiped it.
  describe('a first message in a new conversation whose record arrives late', () => {
    const CARD = {
      id: '3f2504e0-4f89-41d3-9a0c-0305e82c3330',
      toolName: 'log_watch',
      input: { title: 'The Quiet Engine', rating: 4 },
    }

    function record(pendingToolCalls: (typeof CARD)[]) {
      return {
        id: CREATED_ID,
        title: 'New conversation',
        createdAt: '2026-09-10T12:00:00Z',
        updatedAt: '2026-09-10T12:00:00Z',
        messages: [],
        pendingToolCalls,
      }
    }

    function deferred<T>() {
      let resolve!: (value: T) => void
      const promise = new Promise<T>((done) => {
        resolve = done
      })
      return { promise, resolve }
    }

    /** Ask the first question on a blank page, the stream raising a card. */
    async function askForAWrite(stream: AsyncGenerator<unknown>) {
      mocks.streamAiMessage.mockImplementation(() => stream)
      renderPage('/assistant')
      await act(async () => {})
      fireEvent.change(screen.getByLabelText('Message to the assistant'), {
        target: { value: 'I watched The Quiet Engine and give it 4 stars' },
      })
      fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
      expect(await screen.findByText('Can I do this?')).not.toBeNull()
    }

    async function settle() {
      for (let tick = 0; tick < 5; tick += 1) await act(async () => {})
    }

    it('keeps the card when the record lands while the stream is still open', async () => {
      const late = deferred<ReturnType<typeof record>>()
      const streamEnds = deferred<void>()
      mocks.fetchAiConversation
        .mockReset()
        .mockReturnValueOnce(late.promise)
        // Asked for after the stream closed: the server has written the card by then.
        .mockResolvedValue(record([CARD]))
      await askForAWrite(
        (async function* () {
          yield { kind: 'confirm' as const, text: '', toolCalls: [CARD] }
          await streamEnds.promise
        })(),
      )

      late.resolve(record([]))
      await settle()
      expect(screen.getByText('Can I do this?')).not.toBeNull()

      streamEnds.resolve()
      await settle()
      expect(screen.getByText('Can I do this?')).not.toBeNull()
      expect(screen.getByRole('button', { name: /Yes, do it/ })).not.toBeNull()
    })

    it('keeps the card when the record lands after the stream has closed, and asks again', async () => {
      const late = deferred<ReturnType<typeof record>>()
      const streamEnds = deferred<void>()
      mocks.fetchAiConversation
        .mockReset()
        .mockReturnValueOnce(late.promise)
        .mockResolvedValue(record([CARD]))
      await askForAWrite(
        (async function* () {
          yield { kind: 'confirm' as const, text: '', toolCalls: [CARD] }
          await streamEnds.promise
        })(),
      )
      // The record was asked for while the stream was open, before the server held the card.
      await vi.waitFor(() => expect(mocks.fetchAiConversation).toHaveBeenCalledTimes(1))
      streamEnds.resolve()
      await settle()

      late.resolve(record([]))
      await settle()

      expect(screen.getByText('Can I do this?')).not.toBeNull()
      // The early record was set aside and the conversation read again.
      await vi.waitFor(() => expect(mocks.fetchAiConversation).toHaveBeenCalledTimes(2))
      await settle()
      expect(screen.getByText('Can I do this?')).not.toBeNull()
    })
  })
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}
async function ready(path = `/assistant?c=${CONVERSATION_ID}`) {
  renderPage(path)
  await vi.waitFor(() => expect(screen.queryByText('Checking assistant availability…')).toBeNull())
  if (path.includes('?c=')) await screen.findByText('Jaws is on shelf B4.')
}
function draft() { return screen.getByLabelText('Message to the assistant') as HTMLTextAreaElement }
function sendButton() { return screen.getByRole('button', { name: 'Send message' }) as HTMLButtonElement }
function ask(text: string) {
  fireEvent.change(draft(), { target: { value: text } })
  fireEvent.click(sendButton())
}

describe('AA9 selected layout and recovery', () => {
  it.each(['viewer', 'admin'] as const)('offers role-aware starters on a blank landing for %s without creating a chat', async role => {
    mocks.role = role
    await ready('/assistant')
    expect(screen.getByRole('heading', { name: 'Ask about your collection' })).not.toBeNull()
    expect(screen.getByText(role === 'admin' ? /You can also add to the shared wanted list/ : /You can read the shared wanted list/)).not.toBeNull()
    if (role === 'viewer') expect(screen.queryByText(/You can also add/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Unwatched 4Ks' }))
    expect(draft().value).toBe('Which 4Ks have I not watched?')
    expect(draft().tagName).toBe('TEXTAREA')
    expect(mocks.createAiConversation).not.toHaveBeenCalled()
    expect(mocks.streamAiMessage).not.toHaveBeenCalled()
  })

  it.each(['unconfigured', 'status error', 'usage error'] as const)('keeps an editable draft but prevents sending when availability is %s', async state => {
    if (state === 'unconfigured') mocks.fetchAiStatus.mockResolvedValue({ configured: false, model: 'test' })
    if (state === 'status error') mocks.fetchAiStatus.mockRejectedValue(new Error('status unreachable'))
    if (state === 'usage error') mocks.fetchAiUsage.mockRejectedValue(new Error('usage unreachable'))
    await ready('/assistant')
    fireEvent.change(draft(), { target: { value: 'Keep this question' } })
    expect(draft().disabled).toBe(false)
    expect(sendButton().disabled).toBe(true)
    expect(screen.getByRole('alert').textContent).toContain(state === 'unconfigured' ? 'assistant is unavailable' : 'availability is unknown')
    expect(mocks.streamAiMessage).not.toHaveBeenCalled()
  })

  it('shows the spending limit even with calls left and explains the call/reset meaning', async () => {
    mocks.fetchAiUsage.mockResolvedValue({ messages: 1, messageCap: 50, messagesRemaining: 49, costUsd: '2.00', costCapUsd: '2.00', blocked: true, limitMessage: 'Today’s spending limit is reached.', resetsAt: '2026-10-28T00:00:00Z' })
    await ready('/assistant')
    expect(screen.getByText(/AI calls: 49 of 50 left today/)).not.toBeNull()
    expect(screen.getByText(/One question can use more than one call/)).not.toBeNull()
    expect(screen.getByRole('alert').textContent).toContain('spending limit')
    fireEvent.change(draft(), { target: { value: 'Another question' } })
    expect(sendButton().disabled).toBe(true)
  })

  it('keeps a draft offline and makes its connection requirement explicit', async () => {
    await ready('/assistant')
    fireEvent.change(draft(), { target: { value: 'Offline draft' } })
    fireEvent(window, new Event('offline'))
    expect(screen.getByText(/You are offline/)).not.toBeNull()
    expect(draft().value).toBe('Offline draft')
    expect(sendButton().disabled).toBe(true)
    fireEvent(window, new Event('online'))
    expect(sendButton().disabled).toBe(false)
  })

  it('preserves separate drafts when choosing chats and creates nothing for New chat', async () => {
    await ready()
    fireEvent.change(draft(), { target: { value: 'Existing chat draft' } })
    fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
    expect(draft().value).toBe('')
    fireEvent.change(draft(), { target: { value: 'New chat draft' } })
    fireEvent.click(screen.getByRole('button', { name: 'Recent chats' }))
    fireEvent.click(screen.getByRole('button', { name: /Archive questions 10/ }))
    expect(draft().value).toBe('Existing chat draft')
    fireEvent.click(screen.getByRole('button', { name: 'New chat' }))
    expect(draft().value).toBe('New chat draft')
    expect(mocks.createAiConversation).not.toHaveBeenCalled()
  })

  it('makes history failures reachable from the conversation and reloads them', async () => {
    mocks.fetchAiConversations.mockRejectedValueOnce(new Error('History is down'))
    await ready('/assistant')
    const pane = screen.getByRole('region', { name: 'Assistant conversation' })
    expect(within(pane).getByRole('alert').textContent).toContain('Recent chats unavailable')
    fireEvent.click(within(pane).getByRole('button', { name: 'Reload recent chats' }))
    await vi.waitFor(() => expect(within(pane).queryByRole('alert')).toBeNull())
    expect(screen.getByRole('button', { name: /Archive questions 10/ })).not.toBeNull()
  })

  it('requires named-chat deletion confirmation and submits only once', async () => {
    const removed = deferred<void>()
    mocks.deleteAiConversation.mockReturnValue(removed.promise)
    await ready()
    fireEvent.click(screen.getByRole('button', { name: 'Delete this conversation' }))
    const dialog = screen.getByRole('dialog', { name: 'Delete conversation' })
    expect(within(dialog).getByText('Archive questions')).not.toBeNull()
    expect(within(dialog).getByText(/Viewings and Wanted additions you already confirmed stay recorded/)).not.toBeNull()
    expect(mocks.deleteAiConversation).not.toHaveBeenCalled()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Keep chat' }))
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Delete this conversation' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete chat' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete chat' }))
    await vi.waitFor(() => expect(mocks.deleteAiConversation).toHaveBeenCalledTimes(1))
    expect(mocks.deleteAiConversation).toHaveBeenCalledWith(CONVERSATION_ID)
    await act(async () => removed.resolve())
    await vi.waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })

  it('isolates a finishing reply/card from a browser-history change to another chat', async () => {
    const release = deferred<void>()
    const other = '3f2504e0-4f89-41d3-9a0c-0305e82c3309'
    const otherCard = { id: 'other-card', toolName: 'log_watch', input: { title: 'Other film' } }
    const original = await mocks.fetchAiConversation()
    mocks.fetchAiConversation.mockImplementation(async (id: string) => id === other ? { ...original, id: other, title: 'Other chat', messages: [{ role: 'assistant', text: 'Other chat answer', sequence: 1 }], pendingToolCalls: [otherCard] } : original)
    mocks.streamAiMessage.mockImplementationOnce(() => (async function* () {
      await release.promise
      yield { kind: 'text', text: 'Origin chat answer' }
      yield { kind: 'confirm', text: '', toolCalls: [{ id: 'origin-card', toolName: 'log_watch', input: { title: 'Origin film' } }] }
    })())
    await ready()
    ask('Origin question')
    expect((screen.getByRole('button', { name: 'New chat' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Delete this conversation' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Browser history to another chat' }))
    expect(await screen.findByText('Other chat answer')).not.toBeNull()
    await act(async () => release.resolve())
    const log = screen.getByRole('log')
    expect(within(log).queryByText('Origin chat answer')).toBeNull()
    expect(within(log).getAllByText('Can I do this?')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: /Yes, do it/ }))
    await vi.waitFor(() => expect(mocks.resolveAiToolCall).toHaveBeenCalledWith('other-card', true))
  })

  it('does not silently accept a stream with no terminal frame or resend a stored question', async () => {
    const original = await mocks.fetchAiConversation()
    mocks.streamAiMessage.mockImplementationOnce(() => (async function* () { yield { kind: 'text', text: 'Partial reply' } })())
    await ready()
    ask('A question that might be saved')
    expect(await screen.findByText('The assistant response ended before it was complete.')).not.toBeNull()
    expect(draft().value).toBe('A question that might be saved')
    expect(sendButton().disabled).toBe(true)
    expect(mocks.streamAiMessage).toHaveBeenCalledTimes(1)
    mocks.fetchAiConversation.mockResolvedValue({ ...original, messages: [...original.messages, { role: 'user', text: 'A question that might be saved', sequence: 3 }, { role: 'assistant', text: 'Saved partial reply', sequence: 4 }] })
    fireEvent.click(screen.getByRole('button', { name: 'Reload conversation' }))
    expect(await screen.findByText(/Your question is already saved/)).not.toBeNull()
    expect(screen.getByText('Saved partial reply')).not.toBeNull()
    expect(sendButton().disabled).toBe(true)
    expect(draft().value).toBe('A question that might be saved')
    fireEvent.click(screen.getByRole('button', { name: 'Start a different question' }))
    expect(draft().value).toBe('')
    expect(mocks.streamAiMessage).toHaveBeenCalledTimes(1)
  })

  it('permits an explicit resend only after reload proves the question was not saved', async () => {
    mocks.streamAiMessage.mockImplementationOnce(() => (async function* () { throw new Error('Lost reply') })())
    await ready()
    ask('Keep this unsaved draft')
    await screen.findByText('Lost reply')
    fireEvent.click(screen.getByRole('button', { name: 'Reload conversation' }))
    expect(await screen.findByText(/Your question was not saved/)).not.toBeNull()
    expect(draft().value).toBe('Keep this unsaved draft')
    expect(sendButton().disabled).toBe(false)
    expect(mocks.streamAiMessage).toHaveBeenCalledTimes(1)
    fireEvent.click(sendButton())
    await vi.waitFor(() => expect(mocks.streamAiMessage).toHaveBeenCalledTimes(2))
  })

  it('keeps the recovery guard if reloading itself fails', async () => {
    mocks.streamAiMessage.mockImplementationOnce(() => (async function* () { throw new Error('Lost reply') })())
    await ready()
    ask('Keep the guarded draft')
    await screen.findByText('Lost reply')
    await act(async () => {})
    mocks.fetchAiConversation.mockRejectedValue(new Error('Reload unavailable'))
    fireEvent.click(screen.getByRole('button', { name: 'Reload conversation' }))
    expect(await screen.findByText('Reload unavailable')).not.toBeNull()
    expect(draft().value).toBe('Keep the guarded draft')
    expect(sendButton().disabled).toBe(true)
    expect(mocks.streamAiMessage).toHaveBeenCalledTimes(1)
  })

  it('does not repeat a confirmation whose answer was lost', async () => {
    const original = await mocks.fetchAiConversation()
    const card = { id: 'waiting-card', toolName: 'log_watch', input: { title: 'Jaws' } }
    mocks.fetchAiConversation.mockResolvedValueOnce({ ...original, pendingToolCalls: [card] }).mockResolvedValue({ ...original, pendingToolCalls: [] })
    mocks.resolveAiToolCall.mockImplementationOnce(() => (async function* () { throw new Error('Confirmation disconnected') })())
    await ready()
    await screen.findByText('Can I do this?')
    fireEvent.click(screen.getByRole('button', { name: /Yes, do it/ }))
    await screen.findByText('Confirmation disconnected')
    fireEvent.click(screen.getByRole('button', { name: 'Reload conversation' }))
    expect(await screen.findByText(/A confirmed action may already have run/)).not.toBeNull()
    expect(mocks.resolveAiToolCall).toHaveBeenCalledTimes(1)
    expect(mocks.resolveAiToolCall).toHaveBeenCalledWith('waiting-card', true)
  })

  it('does not pull a reader down when another answer fragment arrives', async () => {
    const release = deferred<void>()
    mocks.streamAiMessage.mockImplementationOnce(() => (async function* () {
      yield { kind: 'text', text: 'First fragment' }
      await release.promise
      yield { kind: 'text', text: ' and second fragment' }
      yield { kind: 'done', text: '' }
    })())
    await ready()
    ask('A long answer')
    await screen.findByText('First fragment')
    const log = screen.getByRole('log')
    Object.defineProperty(log, 'scrollHeight', { configurable: true, value: 1000 })
    Object.defineProperty(log, 'clientHeight', { configurable: true, value: 200 })
    log.scrollTop = 100
    fireEvent.scroll(log)
    await act(async () => release.resolve())
    expect(log.scrollTop).toBe(100)
    fireEvent.click(screen.getByRole('button', { name: 'Latest answer' }))
    expect(log.scrollTop).toBe(1000)
  })
})
