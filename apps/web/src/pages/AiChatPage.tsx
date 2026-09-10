import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Check, Loader2, MessageSquarePlus, Send, Trash2, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import type { AiPendingToolCall } from '@mcu/shared'

import { MicButton } from '@/components/MicButton'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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

  // A pending confirmation outlives the stream that raised it — somebody can close the
  // tab mid-prompt and come back to it.
  useEffect(() => {
    if (detail.data) setPending(detail.data.pendingToolCalls)
  }, [detail.data])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [liveTurns, detail.data])

  const startNew = useMutation({
    mutationFn: createAiConversation,
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
      setLiveTurns([])
      setPending([])
      setParams({ c: created.id })
    },
  })

  const remove = useMutation({
    mutationFn: (id: string) => deleteAiConversation(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
      setParams({})
      setLiveTurns([])
    },
  })

  /** Drain a stream into the live transcript. Shared by asking and by confirming. */
  const consume = useCallback(
    async (events: AsyncGenerator<ChatStreamEvent>) => {
      setStreaming(true)
      setError(null)
      let assistant = ''
      let started = false
      try {
        for await (const event of events) {
          if (event.kind === 'text') {
            assistant += event.text
            setLiveTurns((turns) => {
              const next = [...turns]
              if (started) next[next.length - 1] = { role: 'assistant', text: assistant }
              else next.push({ role: 'assistant', text: assistant })
              return next
            })
            started = true
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
      } finally {
        setStreaming(false)
        void queryClient.invalidateQueries({ queryKey: ['ai-conversation', conversationId] })
        void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
        void queryClient.invalidateQueries({ queryKey: ['ai-usage'] })
      }
    },
    [conversationId, queryClient],
  )

  const send = useCallback(async () => {
    const question = prompt.trim()
    if (!question || streaming) return

    let target = conversationId
    if (!target) {
      const created = await createAiConversation()
      target = created.id
      setParams({ c: created.id })
    }
    setPrompt('')
    setLiveTurns((turns) => [...turns, { role: 'user', text: question }])
    await consume(streamAiMessage(target, question))
  }, [conversationId, consume, prompt, setParams, streaming])

  const resolve = useCallback(
    async (call: AiPendingToolCall, confirm: boolean) => {
      setPending((calls) => calls.filter((candidate) => candidate.id !== call.id))
      if (!confirm) {
        setLiveTurns((turns) => [
          ...turns,
          { role: 'user', text: 'No, do not do that.' },
        ])
      }
      await consume(resolveAiToolCall(call.id, confirm))
    },
    [consume],
  )

  const stored = (detail.data?.messages ?? []).filter((message) => message.role !== 'tool_result')
  // While streaming, the live transcript is ahead of what the server has stored.
  const transcript: Turn[] =
    liveTurns.length > 0
      ? liveTurns
      : stored.map((message) => ({
          role: message.role === 'assistant' ? 'assistant' : 'user',
          text: message.text,
        }))

  return (
    <div className="mx-auto flex h-[calc(100vh-6rem)] max-w-5xl gap-4 p-4">
      <aside className="hidden w-56 shrink-0 flex-col gap-2 md:flex">
        <Button size="sm" onClick={() => startNew.mutate()} disabled={startNew.isPending}>
          <MessageSquarePlus className="mr-2 h-4 w-4" aria-hidden />
          New chat
        </Button>
        <ul className="flex-1 space-y-1 overflow-y-auto">
          {conversations.data?.items.map((item) => (
            <li key={item.id} className="group flex items-center gap-1">
              <button
                type="button"
                onClick={() => {
                  setLiveTurns([])
                  setPending([])
                  setParams({ c: item.id })
                }}
                className={cn(
                  'min-w-0 flex-1 truncate rounded px-2 py-1.5 text-left text-sm',
                  item.id === conversationId ? 'bg-muted font-medium' : 'hover:bg-muted/60',
                )}
              >
                {item.title}
              </button>
              <button
                type="button"
                aria-label={`Delete ${item.title}`}
                className="opacity-0 transition-opacity group-hover:opacity-100"
                onClick={() => remove.mutate(item.id)}
              >
                <Trash2 className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="mb-2 flex items-baseline justify-between gap-2">
          <h1 className="flex items-center gap-2 text-lg font-semibold">
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
          <p className="mb-2 rounded border border-destructive/40 bg-destructive/5 p-3 text-sm">
            The assistant is not configured on the server — there is no API key set.
          </p>
        ) : null}

        <div className="flex-1 space-y-3 overflow-y-auto rounded-lg border border-border p-4">
          {transcript.length === 0 && !streaming ? (
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
                  ? 'ml-auto bg-primary/10'
                  : 'mr-auto bg-muted',
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
              className="rounded-lg border border-amber-500/50 bg-amber-500/5 p-3"
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

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {detail.isError ? (
            <p className="text-sm text-destructive">
              {queryErrorMessage(detail.error, 'That conversation could not be loaded.')}
            </p>
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
            placeholder="Which 4Ks have I not watched?"
            disabled={streaming}
            onChange={(event) => setPrompt(event.target.value)}
          />
          {/* §9.5. Dictation fills the box; it never sends. The engine mishears, and the
              person reading what was heard before pressing send is both the safety net and
              the thing that makes "correct transcription" checkable. */}
          <MicButton
            disabled={streaming}
            onTranscript={(text) =>
              setPrompt((current) => (current ? `${current} ${text}` : text))
            }
          />
          <Button type="submit" disabled={streaming || !prompt.trim()}>
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
