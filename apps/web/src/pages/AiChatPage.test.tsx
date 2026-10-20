// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AiChatPage from './AiChatPage'

const mocks = vi.hoisted(() => ({
  createAiConversation: vi.fn(),
  deleteAiConversation: vi.fn(),
  fetchAiConversation: vi.fn(),
  fetchAiConversations: vi.fn(),
  fetchAiStatus: vi.fn(),
  fetchAiUsage: vi.fn(),
  resolveAiToolCall: vi.fn(),
  streamAiMessage: vi.fn(),
}))

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
  yield* []
}

function renderPage(path = `/assistant?c=${CONVERSATION_ID}`) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AiChatPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
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
    expect(screen.getByLabelText('Choose conversation')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Create a new conversation' })).not.toBeNull()

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

    const input = screen.getByLabelText('Message to the assistant') as HTMLInputElement
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
    expect(screen.getByText('Recommend one.')).not.toBeNull()
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
    const input = screen.getByLabelText('Message to the assistant') as HTMLInputElement
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
