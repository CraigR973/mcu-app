import {
  addCollectionItem,
  ApiError,
  deleteCollectionItem,
  fetchCopies,
  NetworkError,
  StaleEditError,
  updateCollectionItem,
  type AddCollectionItemInput,
  type CollectionItemFields,
  type UpdateCollectionItemInput,
} from './api'
import {
  enqueue,
  listQueue,
  queueIsAvailable,
  removeFromQueue,
  updateQueued,
  type QueuedWrite,
} from './offline-queue'

/**
 * Sending the queue, and working out what an unanswered write actually did.
 *
 * The rules this file implements, in one place because they are easy to get subtly and
 * expensively wrong:
 *
 * 1. **A refusal is an answer.** A 4xx means the server saw the write and said no. Stop,
 *    record why, and let the person decide. Never retry.
 * 2. **Offline is not failure.** If the browser says it never sent the request, the entry
 *    stays `queued` and the flush stops — there is no point trying the rest.
 * 3. **Silence is a question, not a failure.** A request that left and got nothing back
 *    becomes `unconfirmed` and is *read back*, never re-sent. Re-sending a create that
 *    landed makes a second disc; re-sending an edit that landed can revert a newer one.
 * 4. **Order is preserved and a failure halts the flush.** Writes replay oldest-first and
 *    a stuck entry stops the ones behind it, because a later edit of the same disc must
 *    not overtake the create that gives it an id.
 */

/** How the UI hears about queue changes without polling IndexedDB. */
type Listener = () => void
const listeners = new Set<Listener>()

export function subscribeToQueue(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function announce(): void {
  for (const listener of listeners) listener()
}

export interface FlushResult {
  sent: number
  /** Entries left behind, each with a reason the person can read. */
  remaining: number
  /** True when the flush stopped because the network is still away. */
  stillOffline: boolean
}

function describeAdd(input: AddCollectionItemInput): string {
  return `Add a disc (${input.formats.join(' + ')})`
}

/**
 * Add a disc, queueing it if the network is not there.
 *
 * Returns the created item when it went straight through, or `null` when it was queued —
 * the caller shows the optimistic row in that case.
 */
export async function addOrQueue(
  input: AddCollectionItemInput,
): Promise<{ item: Awaited<ReturnType<typeof addCollectionItem>> | null; queued: boolean }> {
  try {
    return { item: await addCollectionItem(input), queued: false }
  } catch (error) {
    if (!(error instanceof NetworkError) || !queueIsAvailable()) throw error
    await enqueue({
      operation: 'create',
      movieId: input.movieId,
      label: describeAdd(input),
      body: input,
      // A request that may have landed must not be replayed blind; one the browser
      // never sent is safe to send again the moment there is a connection.
      state: error.mayHaveLanded ? 'unconfirmed' : 'queued',
    })
    announce()
    return { item: null, queued: true }
  }
}

export async function updateOrQueue(
  itemId: string,
  movieId: string,
  input: UpdateCollectionItemInput,
): Promise<{ queued: boolean }> {
  try {
    await updateCollectionItem(itemId, input)
    return { queued: false }
  } catch (error) {
    if (!(error instanceof NetworkError) || !queueIsAvailable()) throw error
    await enqueue({
      operation: 'update',
      itemId,
      movieId,
      label: 'Edit a disc',
      body: input,
      state: error.mayHaveLanded ? 'unconfirmed' : 'queued',
    })
    announce()
    return { queued: true }
  }
}

export async function deleteOrQueue(
  itemId: string,
  movieId: string,
): Promise<{ queued: boolean }> {
  try {
    await deleteCollectionItem(itemId)
    return { queued: false }
  } catch (error) {
    if (!(error instanceof NetworkError) || !queueIsAvailable()) throw error
    await enqueue({
      operation: 'delete',
      itemId,
      movieId,
      label: 'Remove a disc',
      body: {},
      state: error.mayHaveLanded ? 'unconfirmed' : 'queued',
    })
    announce()
    return { queued: true }
  }
}

function sameDisc(copy: { formats: string[]; location: string | null }, body: unknown): boolean {
  const fields = body as Partial<CollectionItemFields>
  const formats = fields.formats ?? []
  return (
    copy.formats.length === formats.length &&
    copy.formats.every((format) => formats.includes(format)) &&
    (copy.location ?? null) === (fields.location ?? null)
  )
}

/**
 * Settle an `unconfirmed` entry by reading the server, never by re-sending.
 *
 * Returns `'landed'`, `'absent'` (so the entry can safely go back to `queued`), or
 * `'unknown'` when the read itself could not be made.
 */
async function reconcile(entry: QueuedWrite): Promise<'landed' | 'absent' | 'unknown'> {
  if (entry.movieId === undefined) return 'unknown'
  let copies: Awaited<ReturnType<typeof fetchCopies>>
  try {
    copies = await fetchCopies(entry.movieId)
  } catch {
    // Still unreachable. Staying `unconfirmed` is the correct answer: reporting a guess
    // here is the failure this whole mechanism exists to avoid.
    return 'unknown'
  }

  if (entry.operation === 'delete') {
    return copies.some((copy) => copy.id === entry.itemId) ? 'absent' : 'landed'
  }
  if (entry.operation === 'update') {
    const current = copies.find((copy) => copy.id === entry.itemId)
    if (current === undefined) return 'unknown'
    return sameDisc(current, entry.body) ? 'landed' : 'absent'
  }
  // A create has no id to look for, so identity is "a live copy of this film that looks
  // like what was being added". Imperfect where the owner genuinely holds two identical
  // discs in one place, which is why a create that reads as absent goes back to `queued`
  // rather than being re-sent from here: the duplicate guard still gets its say.
  return copies.some((copy) => sameDisc(copy, entry.body)) ? 'landed' : 'absent'
}

async function replay(entry: QueuedWrite): Promise<void> {
  if (entry.operation === 'create') {
    await addCollectionItem(entry.body as AddCollectionItemInput)
    return
  }
  if (entry.operation === 'update') {
    await updateCollectionItem(entry.itemId ?? '', entry.body as UpdateCollectionItemInput)
    return
  }
  await deleteCollectionItem(entry.itemId ?? '')
}

let flushing: Promise<FlushResult> | null = null

/**
 * Send everything the queue is holding.
 *
 * Safe to call at any time — on reconnect, on app start, or from the sync panel. Nothing
 * here re-sends a write whose fate is unknown.
 *
 * **One flush at a time** (Batch 38). `online` can fire twice, and "Sync now" can be pressed
 * while the automatic flush is running; two flushes read the same queue and both replayed the
 * same disc, which the server turned into a duplicate question. A second call now joins the
 * flush already under way and gets its result.
 */
export function flushQueue(): Promise<FlushResult> {
  if (flushing) return flushing
  const run = flushOnce().finally(() => {
    flushing = null
  })
  flushing = run
  return run
}

async function flushOnce(): Promise<FlushResult> {
  if (!queueIsAvailable()) return { sent: 0, remaining: 0, stillOffline: false }

  const entries = await listQueue()
  let sent = 0

  for (const entry of entries) {
    if (entry.id === undefined) continue

    if (entry.state === 'unconfirmed') {
      const verdict = await reconcile(entry)
      if (verdict === 'landed') {
        await removeFromQueue(entry.id)
        sent += 1
        continue
      }
      if (verdict === 'unknown') break
      // Demonstrably not on the server, so sending it again can no longer overwrite
      // anything. It falls through to the replay below.
      await updateQueued(entry.id, { state: 'queued', error: undefined })
    }

    try {
      await replay({ ...entry, state: 'queued' })
      await removeFromQueue(entry.id)
      sent += 1
    } catch (error) {
      if (error instanceof NetworkError) {
        if (error.mayHaveLanded) await updateQueued(entry.id, { state: 'unconfirmed' })
        announce()
        return {
          sent,
          remaining: (await listQueue()).length,
          stillOffline: !error.mayHaveLanded,
        }
      }
      // An answer. Record it and stop: entries behind this one may depend on it, and a
      // person who has to make a decision should be shown one decision, not five.
      const message =
        error instanceof StaleEditError
          ? 'This disc changed while your edit was waiting. Your change was not applied.'
          : error instanceof ApiError || error instanceof Error
            ? error.message
            : 'This change could not be saved.'
      await updateQueued(entry.id, { error: message })
      break
    }
  }

  announce()
  return { sent, remaining: (await listQueue()).length, stillOffline: false }
}

/** Drop one entry the person has decided against. */
export async function discardQueued(id: number): Promise<void> {
  await removeFromQueue(id)
  announce()
}

/** Clear a recorded failure so the next flush tries the entry again. */
export async function retryQueued(id: number): Promise<void> {
  await updateQueued(id, { error: undefined })
  announce()
}

/**
 * Flush whenever the connection comes back.
 *
 * Registered once from the app shell. Returns its own unsubscribe so a test can install
 * and remove it without leaking a listener between cases.
 */
export function startAutoFlush(onFlushed?: (result: FlushResult) => void): () => void {
  const run = () => {
    void flushQueue().then((result) => onFlushed?.(result))
  }
  window.addEventListener('online', run)
  return () => window.removeEventListener('online', run)
}
