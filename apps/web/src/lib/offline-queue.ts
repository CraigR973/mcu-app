import { openDB, type DBSchema, type IDBPDatabase } from 'idb'

/**
 * The durable write queue — roadmap §13.9.
 *
 * ## The two states, and why the distinction is the whole design
 *
 * Ported from `the-coupon`'s `usePickEditor`, whose reasoning transfers even though its
 * storage does not:
 *
 * - **`queued`** — the write never left the device. The server cannot possibly hold it,
 *   so sending it again is free of consequence. **Flushed automatically on reconnect.**
 * - **`unconfirmed`** — the write left and nothing came back. The server may or may not
 *   have applied it. **Never re-sent automatically**, because a blind retry of an
 *   `add` that did land creates a second disc, and a blind retry of an `edit` can undo a
 *   change the person made afterwards. Reconnecting *reads the row back* and turns the
 *   unknown into a fact; only the owner re-sends.
 *
 * The naive alternative — optimistic-with-rollback — cannot express `unconfirmed` at all.
 * It has exactly two outcomes, success and failure, so it must guess which one silence
 * means. That is why the batch definition rejects it (`DECISIONS.md` #39).
 *
 * ## Why IndexedDB here, where `the-coupon` chose memory
 *
 * `the-coupon` deliberately keeps its queue in memory: its queue is a *single slot* (one
 * pick per member per round), its data is other members', and an intent outliving a
 * sign-out would fire under whoever holds the phone next.
 *
 * None of that holds here. §13.9 asks for IndexedDB by name; this queue holds several
 * entity types and several pending writes at once; the data is the owner's own catalogue;
 * and the realistic case — cataloguing a shelf of discs in a garage with no signal, then
 * closing the tab — is exactly the one a memory queue loses. The sign-out risk is
 * answered by {@link clearQueue}, which the auth layer calls.
 */

/** Which write this entry replays. */
export type QueuedOperation = 'create' | 'update' | 'delete'

export interface QueuedWrite {
  /** Monotonic, assigned by IndexedDB. Also the replay order — oldest first. */
  id?: number
  operation: QueuedOperation
  /** The item being changed. Absent for a `create`, which has no id until it lands. */
  itemId?: string
  /** The film the change concerns, so the right caches can be refreshed on flush. */
  movieId?: string
  /** How the person would describe this pending change in the sync list. */
  label: string
  /** The request body, already in the shape the endpoint accepts. */
  body: unknown
  state: 'queued' | 'unconfirmed'
  /** Epoch ms, for ordering and for showing how long something has been waiting. */
  createdAt: number
  /** Set when a flush attempt failed in a way the person has to resolve. */
  error?: string
}

interface McuDB extends DBSchema {
  writes: {
    key: number
    value: QueuedWrite
    indexes: { 'by-state': string }
  }
}

const DB_NAME = 'mcu-offline'
const DB_VERSION = 1
const STORE = 'writes'

let dbPromise: Promise<IDBPDatabase<McuDB>> | null = null

/**
 * How long to wait for a connection before giving up on it.
 *
 * IndexedDB has no timeout of its own: an upgrade blocked by another tab holding an older
 * version open simply never resolves. Observed while testing this batch — a save spun
 * forever behind a spinner that could not stop, with nothing thrown and nothing logged,
 * because the pending promise was cached and every later write joined the same wait.
 * Two tabs open across a schema change is enough to reproduce it (`DECISIONS.md` #46).
 */
const OPEN_TIMEOUT_MS = 5_000

function db(): Promise<IDBPDatabase<McuDB>> {
  dbPromise ??= withTimeout(
    openDB<McuDB>(DB_NAME, DB_VERSION, {
      upgrade(database) {
        const store = database.createObjectStore(STORE, {
          keyPath: 'id',
          autoIncrement: true,
        })
        store.createIndex('by-state', 'state')
      },
      blocked() {
        // Another tab is holding an older version. Say so rather than waiting for it.
        throw new Error('Another tab is using an older version of the offline queue.')
      },
    }),
  ).catch((error: unknown) => {
    // Never cache a failure. A cached rejected promise makes the first bad moment
    // permanent for the life of the page, which is how a transient block becomes an app
    // that can no longer save anything.
    dbPromise = null
    throw error
  })
  return dbPromise
}

function withTimeout<T>(promise: Promise<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('The offline queue did not open in time.')),
      OPEN_TIMEOUT_MS,
    )
    promise.then(
      (value) => {
        clearTimeout(timer)
        resolve(value)
      },
      (error: unknown) => {
        clearTimeout(timer)
        reject(error instanceof Error ? error : new Error(String(error)))
      },
    )
  })
}

/**
 * Whether this browser can hold a queue at all.
 *
 * IndexedDB is absent in some private-browsing modes and throws rather than returning
 * null. Callers use this to degrade to online-only instead of failing a write outright:
 * a person who cannot queue should still be able to edit a disc while they have signal.
 */
export function queueIsAvailable(): boolean {
  try {
    return typeof indexedDB !== 'undefined'
  } catch {
    return false
  }
}

export async function enqueue(write: Omit<QueuedWrite, 'id' | 'createdAt'>): Promise<number> {
  const database = await db()
  return database.add(STORE, { ...write, createdAt: Date.now() })
}

export async function listQueue(): Promise<QueuedWrite[]> {
  const database = await db()
  // Insertion order is replay order: a create followed by an edit of the same disc has
  // to go in that sequence or the edit addresses an id the server has never seen.
  return database.getAll(STORE)
}

export async function removeFromQueue(id: number): Promise<void> {
  const database = await db()
  await database.delete(STORE, id)
}

export async function updateQueued(id: number, patch: Partial<QueuedWrite>): Promise<void> {
  const database = await db()
  const existing = await database.get(STORE, id)
  if (existing === undefined) return
  await database.put(STORE, { ...existing, ...patch, id })
}

/**
 * Empty the queue.
 *
 * Called on sign-out. An unsent write that outlives the session it was made in would
 * fire under whoever signs in next — the objection that kept `the-coupon`'s queue in
 * memory, answered here explicitly rather than by not persisting at all.
 */
export async function clearQueue(): Promise<void> {
  if (!queueIsAvailable()) return
  const database = await db()
  await database.clear(STORE)
}

/** Reset the cached connection. Tests only — a new fake IndexedDB needs a new handle. */
export function resetQueueConnection(): void {
  dbPromise = null
}
