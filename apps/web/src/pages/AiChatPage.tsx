import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Check, Loader2, MessageSquarePlus, Send, Trash2, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import type { AiPendingToolCall } from '@mcu/shared'

import { MicButton } from '@/components/MicButton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { StatePanel } from '@/components/ui/state-panel'
import {
  createAiConversation,
  deleteAiConversation,
  describeToolCall,
  fetchAiConversation,
  fetchAiConversations,
  fetchAiStatus,
  fetchAiUsage,
  resolveAiToolCall,
  streamAiMessage,
  type ChatStreamEvent,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

interface Turn {
  role: 'user' | 'assistant'
  text: string
}

/**
 * §9.3's chat, and §9.4's confirmation where it belongs — in the conversation.
 *
 * **The streamed answer lives in component state, not in the query cache.** It arrives a
 * few characters at a time; writing each fragment through React Query would re-render every
 * consumer of that key on every chunk. The cache is refreshed once, at the end.
 */
export default function AiChatPage() {
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const conversationId = params.get('c')
  const [prompt, setPrompt] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [liveTurns, setLiveTurns] = useState<Turn[]>([])
  const [pending, setPending] = useState<AiPendingToolCall[]>([])
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  const status = useQuery({ queryKey: ['ai-status'], queryFn: fetchAiStatus })
  const conversations = useQuery({
    queryKey: ['ai-conversations'],
    queryFn: fetchAiConversations,
  })
  const detail = useQuery({
    queryKey: ['ai-conversation', conversationId],
    queryFn: () => fetchAiConversation(conversationId as string),
    enabled: Boolean(conversationId),
  })
  const usage = useQuery({ queryKey: ['ai-usage'], queryFn: fetchAiUsage })

  const storedTurns: Turn[] = (detail.data?.messages ?? [])
    .filter((message) => message.role !== 'tool_result')
    // A turn that only called a tool has no words; it showed as an empty bubble above its card.
    .filter((message) => message.role !== 'assistant' || message.text.trim() !== '')
    .map((message) => ({
      role: message.role === 'assistant' ? 'assistant' : 'user',
      text: message.text,
    }))

  // A pending confirmation outlives the stream that raised it — somebody can close the
  // tab mid-prompt and come back to it.
  useEffect(() => {
    if (detail.data) setPending(detail.data.pendingToolCalls)
  }, [detail.data])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
        ? 'auto'
        : 'smooth',
    })
  }, [liveTurns, detail.data])

  const startNew = useMutation({
    mutationFn: createAiConversation,
    onMutate: () => setError(null),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
      setLiveTurns([])
      setPending([])
      setParams({ c: created.id })
    },
    onError: (cause) =>
      setError(queryErrorMessage(cause, 'A new conversation could not be created.')),
  })

  const remove = useMutation({
    mutationFn: (id: string) => deleteAiConversation(id),
    onMutate: () => setError(null),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
      setParams({})
      setLiveTurns([])
      setPending([])
    },
    onError: (cause) =>
      setError(queryErrorMessage(cause, 'That conversation could not be deleted.')),
  })

  const selectConversation = useCallback(
    (id: string | null) => {
      setLiveTurns([])
      setPending([])
      setError(null)
      setParams(id ? { c: id } : {})
    },
    [setParams],
  )

  /** Drain a stream into the live transcript. Shared by asking and by confirming. */
  const consume = useCallback(
    async (targetId: string, events: AsyncGenerator<ChatStreamEvent>) => {
      setStreaming(true)
      setError(null)
      let assistant = ''
      let started = false
      try {
        for await (const event of events) {
          if (event.kind === 'text') {
            assistant += event.text
            // Capture this before scheduling the state update. React may batch functional
            // updaters until after the loop advances; reading the mutable `started` flag
            // inside the updater could then replace the user's question with the answer.
            const replaceLastAssistantTurn = started
            started = true
            setLiveTurns((turns) => {
              const next = [...turns]
              if (replaceLastAssistantTurn) {
                next[next.length - 1] = { role: 'assistant', text: assistant }
              }
              else next.push({ role: 'assistant', text: assistant })
              return next
            })
          } else if (event.kind === 'confirm') {
            setPending(
              (event.toolCalls ?? []).map((call) => ({
                id: call.id,
                toolName: call.toolName,
                input: call.input,
              })),
            )
          } else if (event.kind === 'error') {
            setError(event.text)
          }
        }
      } catch (cause) {
        setError(queryErrorMessage(cause, 'The assistant response was interrupted.'))
      } finally {
        setStreaming(false)
        void queryClient.invalidateQueries({ queryKey: ['ai-conversation', targetId] })
        void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
        void queryClient.invalidateQueries({ queryKey: ['ai-usage'] })
      }
    },
    [queryClient],
  )

  async function send() {
    const question = prompt.trim()
    if (!question || streaming || pending.length > 0) return

    let target = conversationId
    if (!target) {
      try {
        const created = await createAiConversation()
        target = created.id
        setParams({ c: created.id })
        void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
      } catch (cause) {
        setError(queryErrorMessage(cause, 'A new conversation could not be created.'))
        return
      }
    }
    setPrompt('')
    // `liveTurns` is the transcript shown while the cache catches up. When this is the
    // first live turn in an existing conversation, seed it with the stored history rather
    // than replacing that history with the new question.
    setLiveTurns((turns) => [
      ...(turns.length > 0 ? turns : storedTurns),
      { role: 'user', text: question },
    ])
    await consume(target, streamAiMessage(target, question))
  }

  const resolve = useCallback(
    async (call: AiPendingToolCall, confirm: boolean) => {
      setPending((calls) => calls.filter((candidate) => candidate.id !== call.id))
      setLiveTurns((turns) => [
        ...(turns.length > 0 ? turns : storedTurns),
        ...(!confirm
          ? [{ role: 'user' as const, text: 'No, do not do that.' }]
          : []),
      ])
      await consume(conversationId ?? '', resolveAiToolCall(call.id, confirm))
    },
    [consume, conversationId, storedTurns],
  )

  // While streaming, the live transcript is ahead of what the server has stored.
  const transcript: Turn[] = liveTurns.length > 0 ? liveTurns : storedTurns
  // Batch X7 (AI45-02): while a card waits, it is the only thing to answer. Typing instead
  // used to break the conversation for good; the server now closes a waiting card as
  // declined if a message arrives anyway, but the card is the clear way through.
  const awaitingCard = pending.length > 0
  const inputLocked = streaming || awaitingCard

  return (
    <div className="mx-auto flex h-[calc(100dvh-5.5rem)] min-h-[32rem] max-w-6xl gap-5 p-4 sm:p-6">
      <aside
        className="archive-panel hidden w-60 shrink-0 flex-col gap-2 p-2 md:flex"
        aria-label="Assistant conversations"
      >
        <Button type="button" onClick={() => startNew.mutate()} disabled={startNew.isPending}>
          <MessageSquarePlus className="mr-2 h-4 w-4" aria-hidden />
          New chat
        </Button>
        {conversations.isError ? (
          <p role="alert" className="px-2 py-3 text-sm text-destructive">
            {queryErrorMessage(conversations.error, 'Conversations could not be loaded.')}
          </p>
        ) : null}
        <ul className="flex-1 space-y-1 overflow-y-auto" aria-label="Conversation history">
          {conversations.data?.items.map((item) => (
            <li key={item.id} className="group flex items-center gap-1">
              <button
                type="button"
                onClick={() => selectConversation(item.id)}
                aria-current={item.id === conversationId ? 'page' : undefined}
                className={cn(
                  'min-h-11 min-w-0 flex-1 truncate rounded-md px-3 py-2 text-left text-sm',
                  item.id === conversationId
                    ? 'bg-primary/10 font-semibold text-primary'
                    : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
                )}
              >
                {item.title}
              </button>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                aria-label={`Delete ${item.title}`}
                className="h-9 w-9 opacity-60 transition-opacity hover:opacity-100 focus-visible:opacity-100"
                onClick={() => remove.mutate(item.id)}
                disabled={remove.isPending && remove.variables === item.id}
              >
                <Trash2 className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              </Button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col" aria-label="Assistant conversation">
        <div className="mb-3 flex items-center gap-2 md:hidden">
          <label className="sr-only" htmlFor="mobile-conversation">
            Choose conversation
          </label>
          <select
            id="mobile-conversation"
            className="select-control min-w-0 flex-1"
            value={conversationId ?? ''}
            onChange={(event) => selectConversation(event.target.value || null)}
          >
            <option value="">New conversation</option>
            {conversations.data?.items.map((item) => (
              <option key={item.id} value={item.id}>{item.title}</option>
            ))}
          </select>
          <Button
            type="button"
            size="icon"
            variant="outline"
            aria-label="Create a new conversation"
            onClick={() => startNew.mutate()}
            disabled={startNew.isPending}
          >
            {startNew.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <MessageSquarePlus className="h-4 w-4" aria-hidden />
            )}
          </Button>
          {conversationId ? (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              aria-label="Delete this conversation"
              onClick={() => remove.mutate(conversationId)}
              disabled={remove.isPending}
            >
              <Trash2 className="h-4 w-4" aria-hidden />
            </Button>
          ) : null}
        </div>

        <header className="mb-3 flex items-baseline justify-between gap-2 border-b border-border pb-3">
          <h1 className="flex items-center gap-2 font-display text-2xl font-semibold">
            <Bot className="h-5 w-5" aria-hidden />
            {detail.data?.title ?? 'Assistant'}
          </h1>
          {usage.data ? (
            <span className="text-xs text-muted-foreground">
              {usage.data.messagesRemaining} of {usage.data.messageCap} left today
            </span>
          ) : null}
        </header>

        {status.data && !status.data.configured ? (
          <p role="alert" className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
            The assistant is not configured on the server — there is no API key set.
          </p>
        ) : null}

        <div
          className="archive-panel flex-1 space-y-3 overflow-y-auto bg-surface-sunken/25 p-4"
          role="log"
          aria-live="polite"
          aria-busy={streaming}
        >
          {detail.isPending && conversationId && transcript.length === 0 ? (
            <StatePanel compact tone="loading" title="Opening conversation" />
          ) : null}
          {transcript.length === 0 && !streaming && !detail.isPending ? (
            <p className="text-sm text-muted-foreground">
              Ask about the collection — what you own, where it is shelved, what you have
              not watched. It can add to the wanted list and log a viewing too, and it will
              ask before it does either.
            </p>
          ) : null}

          {transcript.map((turn, index) => (
            <div
              key={index}
              className={cn(
                'max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm',
                turn.role === 'user'
                  ? 'ml-auto bg-primary text-primary-foreground'
                  : 'mr-auto border border-border bg-card text-card-foreground',
              )}
            >
              {turn.text}
            </div>
          ))}

          {streaming && transcript[transcript.length - 1]?.role !== 'assistant' ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-hidden />
          ) : null}

          {/* §9.4. Nothing has run at this point — the write happens on Yes and not at all
              on No, and the prompt says what will actually happen rather than naming a
              tool. */}
          {pending.map((call) => (
            <div
              key={call.id}
              className="rounded-lg border border-warning/50 bg-warning/10 p-3"
            >
              <p className="text-sm font-medium">Can I do this?</p>
              <p className="mt-1 text-sm">{describeToolCall(call)}</p>
              <div className="mt-2 flex gap-2">
                <Button size="sm" onClick={() => void resolve(call, true)} disabled={streaming}>
                  <Check className="mr-1 h-3 w-3" aria-hidden />
                  Yes, do it
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void resolve(call, false)}
                  disabled={streaming}
                >
                  <X className="mr-1 h-3 w-3" aria-hidden />
                  No
                </Button>
              </div>
            </div>
          ))}

          {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
          {detail.isError ? (
            <StatePanel
              compact
              tone="error"
              title="Conversation unavailable"
              description={queryErrorMessage(detail.error, 'That conversation could not be loaded.')}
            />
          ) : null}
          <div ref={bottomRef} />
        </div>

        <form
          className="mt-3 flex gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            void send()
          }}
        >
          <Input
            className="min-w-0 flex-1"
            value={prompt}
            maxLength={4000}
            placeholder={awaitingCard ? 'Answer the card above first' : 'Which 4Ks have I not watched?'}
            aria-label="Message to the assistant"
            disabled={inputLocked}
            onChange={(event) => setPrompt(event.target.value)}
          />
          {/* §9.5. Dictation fills the box; it never sends. The engine mishears, and the
              person reading what was heard before pressing send is both the safety net and
              the thing that makes "correct transcription" checkable. */}
          <MicButton
            disabled={inputLocked}
            onTranscript={(text) =>
              setPrompt((current) => (current ? `${current} ${text}` : text))
            }
          />
          <Button
            type="submit"
            size="icon"
            aria-label={streaming ? 'Sending message' : 'Send message'}
            disabled={inputLocked || !prompt.trim()}
          >
            {streaming ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Send className="h-4 w-4" aria-hidden />
            )}
          </Button>
        </form>
      </section>
    </div>
  )
}
