import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, Loader2, MessageSquarePlus, Send, Trash2, X } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import type { AiConversation, AiPendingToolCall } from '@mcu/shared'

import { AssistantHistory } from '@/components/assistant/AssistantHistory'
import { AssistantText } from '@/components/assistant/AssistantText'
import { MicButton } from '@/components/MicButton'
import { usePageTitle } from '@/components/layouts/page-chrome'
import { Button } from '@/components/ui/button'
import { Dialog } from '@/components/ui/dialog'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import {
  createAiConversation, deleteAiConversation, describeToolCall, fetchAiConversation,
  fetchAiConversations, fetchAiStatus, fetchAiUsage, resolveAiToolCall, streamAiMessage,
  type ChatStreamEvent,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { cn, formatDateTime } from '@/lib/utils'

interface Turn { role: 'user' | 'assistant'; text: string }
interface Recovery { question: string | null; since: number; stage: 'reload' | 'saved' }
interface ChatLocal {
  turns: Turn[]
  pending: AiPendingToolCall[] | null
  error: string | null
  recovery?: Recovery
  notice?: string
}
const EMPTY: ChatLocal = { turns: [], pending: null, error: null }
const keyFor = (id: string | null) => id ?? 'new'
const STARTERS = [
  { label: 'Unwatched 4Ks', prompt: 'Which 4Ks have I not watched?' },
  { label: 'Where is a film?', prompt: 'Where is ' },
  { label: 'Log a viewing', prompt: 'I watched ' },
]

/** Conversation first (#300). Streams and recovery belong to a chat, never the current URL. */
export default function AiChatPage() {
  usePageTitle('Assistant')
  const { profile } = useAuth()
  const online = useOnlineStatus()
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const conversationId = params.get('c')
  const selected = useRef(conversationId)
  selected.current = conversationId
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const prompt = drafts[keyFor(conversationId)] ?? ''
  const [locals, setLocals] = useState<Record<string, ChatLocal>>({})
  const local = locals[keyFor(conversationId)] ?? EMPTY
  const [busy, setBusy] = useState(false)
  const busyRef = useRef(false)
  const [activeTarget, setActiveTarget] = useState<string | null>(null)
  const [reloading, setReloading] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [deleting, setDeleting] = useState<AiConversation | null>(null)
  const mounted = useRef(true)
  const logRef = useRef<HTMLDivElement>(null)
  const draftRef = useRef<HTMLTextAreaElement>(null)
  const following = useRef(true)
  const [away, setAway] = useState(false)
  // #287: only a record asked for after this chat's latest stream ended can settle its card.
  const streamsEnded = useRef(new Map<string, number>())
  const askedAfter = useRef(new WeakMap<object, number>())

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])
  const update = useCallback((id: string | null, change: (value: ChatLocal) => ChatLocal) => {
    if (mounted.current) setLocals(values => ({ ...values, [keyFor(id)]: change(values[keyFor(id)] ?? EMPTY) }))
  }, [])
  const writeDraft = useCallback((id: string | null, value: string | ((current: string) => string)) => {
    if (mounted.current) setDrafts(values => ({ ...values, [keyFor(id)]: typeof value === 'function' ? value(values[keyFor(id)] ?? '') : value }))
  }, [])

  const status = useQuery({ queryKey: ['ai-status'], queryFn: fetchAiStatus })
  const conversations = useQuery({ queryKey: ['ai-conversations'], queryFn: fetchAiConversations })
  const usage = useQuery({ queryKey: ['ai-usage'], queryFn: fetchAiUsage })
  const detail = useQuery({
    queryKey: ['ai-conversation', conversationId],
    queryFn: async () => {
      const id = conversationId as string
      const asked = streamsEnded.current.get(id) ?? 0
      const record = await fetchAiConversation(id)
      askedAfter.current.set(record, asked)
      return record
    },
    enabled: Boolean(conversationId),
    structuralSharing: false,
  })
  const refetchDetail = detail.refetch
  const ownReply = busy && activeTarget === conversationId
  const storedTurns: Turn[] = (detail.data?.messages ?? [])
    .filter(message => message.role !== 'tool_result' && (message.role !== 'assistant' || message.text.trim() !== ''))
    .map(message => ({ role: message.role === 'assistant' ? 'assistant' : 'user', text: message.text }))
  const transcript = local.turns.length > 0 ? local.turns : storedTurns
  const pending = local.pending ?? detail.data?.pendingToolCalls ?? []
  const awaitingCard = pending.length > 0
  const opening = Boolean(conversationId) && detail.isPending
  const readFailed = Boolean(conversationId) && detail.isError
  const inputLocked = busy || awaitingCard || Boolean(local.recovery) || opening || readFailed
  const availabilityLocked = !online || status.isPending || status.isError || !status.data?.configured || usage.isPending || usage.isError || usage.data?.blocked

  useEffect(() => {
    const record = detail.data
    if (!record || ownReply || record.id !== conversationId) return
    if ((askedAfter.current.get(record) ?? -1) !== (streamsEnded.current.get(record.id) ?? 0)) {
      void refetchDetail()
      return
    }
    update(record.id, value => {
      const saved = record.messages.filter(message => message.role !== 'tool_result' && (message.role !== 'assistant' || message.text.trim() !== ''))
      const caughtUp = value.turns.length <= saved.length && value.turns.every((turn, index) => saved[index]?.role === turn.role && saved[index]?.text === turn.text)
      return { ...value, pending: record.pendingToolCalls, turns: !value.recovery && caughtUp ? [] : value.turns }
    })
  }, [detail.data, ownReply, conversationId, refetchDetail, update])

  useEffect(() => {
    following.current = true
    setAway(false)
    setHistoryOpen(false)
  }, [conversationId])
  useEffect(() => {
    const node = logRef.current
    if (node && following.current) node.scrollTop = node.scrollHeight
  }, [local.turns, local.pending, local.error, local.recovery, local.notice, detail.data, conversationId, online, status.isPending, status.isError, status.data, usage.isPending, usage.isError, usage.data])

  function selectConversation(id: string | null) {
    if (busyRef.current || remove.isPending) return
    following.current = true
    setAway(false)
    setHistoryOpen(false)
    setParams(id ? { c: id } : {})
  }
  function begin(): boolean {
    if (busyRef.current) return false
    busyRef.current = true
    setBusy(true)
    return true
  }
  function finish() {
    busyRef.current = false
    if (mounted.current) setBusy(false)
  }
  const closeDelete = useCallback(() => { if (!busyRef.current) setDeleting(null) }, [])
  const remove = useMutation({
    mutationFn: (id: string) => deleteAiConversation(id),
    onSettled: finish,
    onSuccess: (_value, id) => {
      void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
      queryClient.removeQueries({ queryKey: ['ai-conversation', id], exact: true })
      writeDraft(id, '')
      update(id, () => EMPTY)
      setDeleting(null)
      if (selected.current === id) setParams({})
    },
  })

  async function consume(target: string, events: AsyncGenerator<ChatStreamEvent>, recovery: Omit<Recovery, 'stage'>) {
    let assistant = ''
    let started = false
    let terminal = false
    let failed = false
    try {
      for await (const event of events) {
        if (event.kind === 'text') {
          assistant += event.text
          const replace = started
          started = true
          const text = assistant
          update(target, value => ({ ...value, turns: replace
            ? [...value.turns.slice(0, -1), { role: 'assistant', text }]
            : [...value.turns, { role: 'assistant', text }] }))
        } else if (event.kind === 'confirm') {
          terminal = true
          update(target, value => ({ ...value, pending: event.toolCalls ?? [] }))
        } else if (event.kind === 'done') {
          terminal = true
        } else if (event.kind === 'error') {
          terminal = true
          failed = true
          update(target, value => ({ ...value, error: event.text, recovery: { ...recovery, stage: 'reload' } }))
        }
      }
      if (!terminal) throw new Error('The assistant response ended before it was complete.')
    } catch (cause) {
      failed = true
      update(target, value => ({ ...value, error: queryErrorMessage(cause, 'The assistant response was interrupted.'), recovery: { ...recovery, stage: 'reload' } }))
    } finally {
      streamsEnded.current.set(target, (streamsEnded.current.get(target) ?? 0) + 1)
      void queryClient.invalidateQueries({ queryKey: ['ai-conversation', target] })
      void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
      void queryClient.invalidateQueries({ queryKey: ['ai-usage'] })
    }
    if (!failed && recovery.question !== null) writeDraft(target, '')
  }

  async function send() {
    const question = prompt.trim()
    if (!question || inputLocked || availabilityLocked || !begin()) return
    const initial = conversationId
    setActiveTarget(initial)
    let target = initial
    try {
      if (!target) {
        update(null, value => ({ ...value, error: null }))
        const created = await createAiConversation()
        target = created.id
        void queryClient.invalidateQueries({ queryKey: ['ai-conversations'] })
        if (!mounted.current) return
        writeDraft(target, question)
        writeDraft(null, '')
        if (selected.current === initial) setParams({ c: target })
      }
      setActiveTarget(target)
      update(target, value => ({ ...value, turns: [...(value.turns.length ? value.turns : storedTurns), { role: 'user', text: question }], error: null, recovery: undefined, notice: undefined }))
      await consume(target, streamAiMessage(target, question), { question, since: detail.data?.messages.at(-1)?.sequence ?? 0 })
    } catch (cause) {
      update(initial, value => ({ ...value, error: queryErrorMessage(cause, 'A new conversation could not be created.') }))
    } finally { finish() }
  }

  async function resolve(call: AiPendingToolCall, confirm: boolean) {
    if (!conversationId || local.recovery || !online || !begin()) return
    const target = conversationId
    setActiveTarget(target)
    update(target, value => ({ ...value, pending: pending.filter(candidate => candidate.id !== call.id), turns: value.turns.length ? value.turns : storedTurns, error: null, notice: undefined }))
    try { await consume(target, resolveAiToolCall(call.id, confirm), { question: null, since: detail.data?.messages.at(-1)?.sequence ?? 0 }) }
    finally { finish() }
  }

  async function reloadConversation() {
    const recovery = local.recovery
    const target = conversationId
    if (!target || !begin()) return
    setReloading(true)
    try {
      const result = await refetchDetail()
      if (!result.isSuccess || !result.data) return
      const saved = recovery?.question !== null && recovery?.question !== undefined && result.data.messages.some(message => message.sequence > recovery.since && message.role === 'user' && message.text === recovery.question)
      update(target, value => ({ ...value, turns: [], pending: result.data.pendingToolCalls, error: null,
        recovery: saved && recovery ? { ...recovery, stage: 'saved' } : undefined,
        notice: saved ? 'Your question is already saved in this chat. Read the stored reply before starting a different question.'
          : recovery?.question ? 'Your question was not saved. You can edit or send the draft below.'
            : recovery ? 'Saved conversation reloaded. A confirmed action may already have run; check this chat and your diary or Wanted before asking again.' : undefined,
      }))
    } finally { if (mounted.current) setReloading(false); finish() }
  }

  function fillStarter(value: string) {
    writeDraft(conversationId, value)
    draftRef.current?.focus()
  }
  function showLatest() {
    following.current = true
    setAway(false)
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }
  const historyError = conversations.isError ? queryErrorMessage(conversations.error, 'Recent chats could not be loaded.') : null

  return (
    <div className="mx-auto flex h-full min-h-0 max-w-6xl gap-4 p-3 sm:p-5" role="region" aria-label="Assistant page">
      <AssistantHistory items={conversations.data?.items ?? []} selectedId={conversationId} loading={conversations.isPending} error={historyError} busy={busy || remove.isPending} open={historyOpen}
        onClose={() => setHistoryOpen(false)} onSelect={selectConversation} onDelete={item => { remove.reset(); setDeleting(item) }} onReload={() => void conversations.refetch()} />
      <section className={cn('min-h-0 min-w-0 flex-1 flex-col gap-3', historyOpen ? 'hidden md:flex' : 'flex')} aria-label="Assistant conversation">
        <header className="max-h-[30%] shrink-0 space-y-2 overflow-y-auto">
          <h1 className="hidden font-display text-2xl font-semibold lg:block">Assistant</h1>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" variant="outline" className="md:hidden" aria-controls="assistant-history" aria-expanded={historyOpen} disabled={busy || remove.isPending} onClick={() => setHistoryOpen(true)}>Recent chats</Button>
            <Button type="button" variant="outline" disabled={busy || remove.isPending} onClick={() => selectConversation(null)}><MessageSquarePlus aria-hidden />New chat</Button>
            {conversationId && detail.data ? <Button type="button" variant="ghost" size="icon" className="ml-auto" aria-label="Delete this conversation" disabled={busy || remove.isPending} onClick={() => { remove.reset(); setDeleting(detail.data) }}><Trash2 aria-hidden /></Button> : null}
          </div>
          {historyError ? <p role="alert" className="text-sm text-destructive">Recent chats unavailable. <button type="button" className="min-h-11 underline" onClick={() => void conversations.refetch()}>Reload recent chats</button></p> : null}
          {usage.data ? <details className="border-b border-border pb-1 text-xs text-muted-foreground"><summary className="flex min-h-11 cursor-pointer items-center">AI calls: {usage.data.messagesRemaining} of {usage.data.messageCap} left today <ChevronDown className="ml-1 h-3 w-3" aria-hidden /></summary><p className="pb-2 leading-5">One question can use more than one call. A daily spending limit also applies. Resets {formatDateTime(usage.data.resetsAt)} in your time zone.</p></details> : null}
        </header>

        <div ref={logRef} className="archive-panel min-h-0 flex-1 space-y-4 overflow-y-auto p-3 sm:p-4" role="log" aria-label="Conversation messages" aria-live={ownReply ? 'off' : 'polite'} aria-busy={ownReply}
          onScroll={event => { const node = event.currentTarget; const near = node.scrollHeight - node.clientHeight - node.scrollTop < 64; following.current = near; setAway(!near) }}>
          {detail.data ? <h2 className="break-words text-sm font-medium [overflow-wrap:anywhere]">{detail.data.title}</h2> : null}
          {opening ? <StatePanel compact tone="loading" title="Opening conversation" /> : null}
          {readFailed ? <StatePanel compact tone="error" title="Conversation unavailable" description={queryErrorMessage(detail.error, 'That conversation could not be loaded.')} action={!local.recovery ? <Button type="button" variant="outline" onClick={() => void reloadConversation()} disabled={busy}>Reload conversation</Button> : undefined} /> : null}
          {!opening && !readFailed && transcript.length === 0 && !ownReply ? <div className="space-y-4 py-2"><div><h2 className="font-display text-2xl font-semibold">Ask about your collection</h2><p className="mt-2 text-sm leading-6 text-muted-foreground">Find films and shelves, check what you have watched, or log your own viewing. {profile?.role === 'admin' ? 'You can also add to the shared wanted list.' : 'You can read the shared wanted list.'} Changes always ask for your confirmation.</p></div><div className="grid gap-2" aria-label="Example questions">{STARTERS.map(starter => <Button key={starter.label} type="button" variant="outline" className="justify-start" disabled={inputLocked} onClick={() => fillStarter(starter.prompt)}>{starter.label}</Button>)}</div></div> : null}
          {transcript.map((turn, index) => <div key={index} className={cn('min-w-0 rounded-lg text-sm', turn.role === 'user' ? 'ml-auto max-w-[92%] whitespace-pre-wrap break-words bg-primary px-3 py-2 text-primary-foreground [overflow-wrap:anywhere]' : 'mr-auto w-full py-1')}>
            {turn.role === 'assistant' ? <AssistantText text={turn.text} /> : turn.text}
          </div>)}
          {busy && !remove.isPending ? <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" aria-hidden />{reloading ? 'Reloading saved conversation…' : ownReply ? 'The assistant is answering…' : 'A reply is finishing. Chat controls will unlock when it ends.'}</p> : null}
          {pending.map(call => <div key={call.id} className="rounded-lg border border-warning/50 bg-warning/10 p-3"><p className="text-sm font-medium">Can I do this?</p><p className="mt-1 break-words text-sm">{describeToolCall(call)}</p><p className="mt-1 text-xs text-muted-foreground">{call.toolName === 'log_watch' ? 'This changes only your diary.' : 'This changes the shared wanted list.'}</p><div className="mt-3 flex flex-wrap gap-2"><Button type="button" size="sm" onClick={() => void resolve(call, true)} disabled={busy || Boolean(local.recovery) || !online}><Check aria-hidden />Yes, do it</Button><Button type="button" size="sm" variant="outline" onClick={() => void resolve(call, false)} disabled={busy || Boolean(local.recovery) || !online}><X aria-hidden />No</Button></div></div>)}
          {!online ? <p role="status" className="text-sm text-muted-foreground">You are offline. Your draft is kept; sending needs a connection.</p>
            : status.isPending || usage.isPending ? <p role="status" className="text-sm text-muted-foreground">Checking assistant availability…</p>
              : status.isError || usage.isError ? <p role="alert" className="text-sm text-destructive">Assistant availability is unknown. Your draft is kept. <button type="button" className="min-h-11 underline" onClick={() => { void status.refetch(); void usage.refetch() }}>Retry availability</button></p>
                : status.data && !status.data.configured ? <p role="alert" className="text-sm text-destructive">The assistant is unavailable. Craig needs to check its server setup. Your draft is kept.</p>
                  : usage.data?.blocked ? <p role="alert" className="text-sm text-destructive">{usage.data.limitMessage ?? 'Today’s AI allowance has been reached. Open the allowance details for its reset time.'}</p> : null}
          {local.error ? <p role="alert" className="break-words text-sm text-destructive">{local.error}</p> : null}
          {local.notice ? <p role="status" className="text-sm text-muted-foreground">{local.notice}</p> : null}
          {local.recovery?.stage === 'reload' ? <div className="space-y-2"><p className="text-sm text-muted-foreground">The answer may already be saved. Reload this chat before deciding what to send next.</p><Button type="button" variant="outline" onClick={() => void reloadConversation()} disabled={busy || !online}>Reload conversation</Button></div> : null}
          {local.recovery?.stage === 'saved' ? <Button type="button" variant="outline" onClick={() => { writeDraft(conversationId, ''); update(conversationId, value => ({ ...value, recovery: undefined, notice: undefined })); draftRef.current?.focus() }}>Start a different question</Button> : null}
        </div>
        {away ? <Button type="button" variant="ghost" size="sm" className="shrink-0" onClick={showLatest}><ChevronDown aria-hidden />Latest answer</Button> : null}

        <div className="shrink-0 space-y-2">
          <form className="rounded-lg border border-input bg-card p-2" onSubmit={event => { event.preventDefault(); void send() }}>
            <label htmlFor="assistant-draft" className="sr-only">Message to the assistant</label>
            <textarea ref={draftRef} id="assistant-draft" className="form-control min-h-16 w-full resize-none border-0 bg-transparent text-base shadow-none" rows={2} maxLength={4000} value={prompt} placeholder={awaitingCard ? 'Answer the card above first' : 'Ask about a film, a shelf or your diary'} disabled={inputLocked} onChange={event => writeDraft(conversationId, event.target.value)} />
            <div className="mt-1 flex items-center justify-end gap-2"><MicButton disabled={inputLocked} onTranscript={text => writeDraft(conversationId, current => current ? `${current} ${text}` : text)} /><Button type="submit" aria-label={busy ? 'Sending message' : 'Send message'} disabled={inputLocked || availabilityLocked || !prompt.trim()}><Send aria-hidden />Send</Button></div>
          </form>
        </div>
      </section>
      <Dialog open={Boolean(deleting)} onClose={closeDelete} label="Delete conversation"><div className="space-y-4 p-5"><h2 className="font-display text-xl font-semibold">Delete this chat?</h2><p className="break-words text-sm">{deleting?.title}</p><p className="text-sm text-muted-foreground">The chat will leave your history. There is no Undo here. Viewings and Wanted additions you already confirmed stay recorded.</p>{remove.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(remove.error, 'That conversation could not be deleted.')}</p> : null}<div className="flex flex-wrap gap-2"><Button type="button" variant="outline" onClick={closeDelete} disabled={remove.isPending}>Keep chat</Button><Button type="button" variant="destructive" disabled={busy || remove.isPending} onClick={() => { if (deleting && begin()) remove.mutate(deleting.id) }}>Delete chat</Button></div></div></Dialog>
    </div>
  )
}
