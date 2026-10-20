import 'fake-indexeddb/auto'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearQueue, listQueue, resetQueueConnection } from './offline-queue'
import { addOrQueue, deleteOrQueue, flushQueue, updateOrQueue } from './sync'

/**
 * The offline queue, tested at the level the acceptance criteria are written at.
 *
 * The distinction these cases exist to protect is `queued` vs `unconfirmed`: a write the
 * browser never sent is safe to send again, and one that left without an answer is not.
 * Getting that backwards duplicates discs and silently reverts edits, and neither failure
 * announces itself.
 */

const copy = {
  id: 'aaaaaaaa-4f89-11d3-9a0c-0305e82c3301',
  formats: ['blu_ray'],
  location: 'Front 2nd shelf',
  section: 'Front',
  shelf: '2nd',
  subCategory: null,
  notes: null,
  purchasePrice: null,
  purchaseSource: null,
  purchaseDate: null,
  condition: 'good',
  hasPlaybackIssues: false,
  playbackNotes: null,
  videoSpecs: null,
  audioSpecs: null,
  specialFeatures: null,
  regionCode: null,
  releaseLabel: null,
  listingStatus: 'in_collection',
  ebayListingUrl: null,
  listingPrice: null,
  updatedAt: '2026-09-08T14:00:00Z',
}

const MOVIE_ID = 'bbbbbbbb-4f89-11d3-9a0c-0305e82c3302'

/** What a write endpoint returns — a superset of the copy shape, and parsed as one. */
const writtenItem = {
  ...copy,
  movieId: MOVIE_ID,
  movieTitle: 'Heat',
  locationLabel: 'Front 2nd',
  conditionUpdatedAt: null,
  deletedAt: null,
}

function itemResponse(status = 200) {
  return new Response(JSON.stringify(writtenItem), { status })
}

function setOnline(value: boolean) {
  vi.stubGlobal('navigator', { onLine: value })
}

/** A fetch that fails the way a browser fails when the device has no connection. */
function offlineFetch() {
  return vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
}

/** A fetch that fails *after* the request went out — the unknown case. */
function droppedFetch() {
  return vi.fn().mockRejectedValue(new TypeError('network error'))
}

beforeEach(async () => {
  resetQueueConnection()
  await clearQueue()
  setOnline(true)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('queueing a write', () => {
  it('marks a write the browser never sent as queued', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())

    const result = await updateOrQueue(copy.id, MOVIE_ID, {
      formats: ['blu_ray'],
      hasPlaybackIssues: false,
    })

    expect(result.queued).toBe(true)
    const [entry] = await listQueue()
    // `navigator.onLine === false` is the one case the browser is authoritative about:
    // it did not attempt the request, so the server cannot be holding it.
    expect(entry.state).toBe('queued')
    expect(entry.operation).toBe('update')
  })

  it('marks a write that left without an answer as unconfirmed', async () => {
    setOnline(true)
    vi.stubGlobal('fetch', droppedFetch())

    await updateOrQueue(copy.id, MOVIE_ID, { formats: ['dvd'], hasPlaybackIssues: false })

    const [entry] = await listQueue()
    // The bytes may have reached the server. Assuming otherwise is what reverts a
    // newer edit, so the unknown case is never treated as a plain failure.
    expect(entry.state).toBe('unconfirmed')
  })

  it('queues an add and a delete the same way', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())

    await addOrQueue({ movieId: MOVIE_ID, formats: ['4k_uhd'], hasPlaybackIssues: false })
    await deleteOrQueue(copy.id, MOVIE_ID)

    const entries = await listQueue()
    expect(entries.map((entry) => entry.operation)).toEqual(['create', 'delete'])
    expect(entries.every((entry) => entry.state === 'queued')).toBe(true)
  })
})

describe('flushing on reconnect', () => {
  it('sends a queued write and clears it — §13.9’s acceptance', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await addOrQueue({ movieId: MOVIE_ID, formats: ['4k_uhd'], hasPlaybackIssues: false })
    expect(await listQueue()).toHaveLength(1)

    setOnline(true)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(itemResponse(201)),
    )

    const result = await flushQueue()

    expect(result.sent).toBe(1)
    expect(await listQueue()).toHaveLength(0)
  })

  it('never re-sends an unconfirmed write — it reads the row back instead', async () => {
    setOnline(true)
    vi.stubGlobal('fetch', droppedFetch())
    await updateOrQueue(copy.id, MOVIE_ID, {
      formats: ['dvd'],
      location: 'Back 6th shelf',
      hasPlaybackIssues: false,
    })

    // The read shows the edit *did* land, so there is nothing left to do.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ ...copy, formats: ['dvd'], location: 'Back 6th shelf' }])),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await flushQueue()

    expect(result.sent).toBe(1)
    expect(await listQueue()).toHaveLength(0)
    // One call, and it was the read. A PUT here would be the bug this whole design exists
    // to prevent.
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit | undefined]
    expect(init?.method ?? 'GET').toBe('GET')
  })

  it('drops an unconfirmed write back to queued when the read proves it never landed', async () => {
    setOnline(true)
    vi.stubGlobal('fetch', droppedFetch())
    await updateOrQueue(copy.id, MOVIE_ID, {
      formats: ['dvd'],
      location: 'Back 6th shelf',
      hasPlaybackIssues: false,
    })

    // The row still holds the old values, so the server demonstrably does not have the
    // edit — which makes sending it again safe for the first time.
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([copy])))
      .mockResolvedValueOnce(itemResponse())
    vi.stubGlobal('fetch', fetchMock)

    const result = await flushQueue()

    expect(result.sent).toBe(1)
    expect(await listQueue()).toHaveLength(0)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe('PUT')
  })

  // CR43-05 (Batch 38). The first send's version of this rule is tested above and in
  // "queueing a write"; the replay's was not: deleting the `mayHaveLanded` step in
  // `flushQueue` left every case green. A replay that reaches the server and loses its answer
  // is exactly what a deploy restart looks like from the phone.
  it('marks a replay whose answer was lost as unconfirmed, and keeps it for the next flush', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await addOrQueue({ movieId: MOVIE_ID, formats: ['4k_uhd'], hasPlaybackIssues: false })
    expect((await listQueue())[0].state).toBe('queued')

    // Back online; the replay goes out and the answer is a 503 from a container restarting.
    setOnline(true)
    const lost = vi.fn().mockResolvedValue(new Response('', { status: 503 }))
    vi.stubGlobal('fetch', lost)

    const result = await flushQueue()

    expect(result.sent).toBe(0)
    expect(lost).toHaveBeenCalledTimes(1)
    const [entry] = await listQueue()
    expect(entry.state).toBe('unconfirmed')
  })

  it('reads a lost replay back instead of sending it a second time', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await addOrQueue({ movieId: MOVIE_ID, formats: ['4k_uhd'], hasPlaybackIssues: false })
    setOnline(true)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })))
    await flushQueue()
    expect((await listQueue())[0].state).toBe('unconfirmed')

    // The shelf now holds the disc: the replay had landed.
    const readBack = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify([{ ...copy, formats: ['4k_uhd'], location: null }])))
    vi.stubGlobal('fetch', readBack)

    const result = await flushQueue()

    expect(result.sent).toBe(1)
    expect(await listQueue()).toHaveLength(0)
    // One call and it was the read: a second POST here is a second disc.
    expect(readBack).toHaveBeenCalledTimes(1)
    const [, init] = readBack.mock.calls[0] as [string, RequestInit | undefined]
    expect(init?.method ?? 'GET').toBe('GET')
  })

  it('sends a queued write once even when two flushes start together', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await addOrQueue({ movieId: MOVIE_ID, formats: ['4k_uhd'], hasPlaybackIssues: false })
    setOnline(true)
    // `online` firing twice, or "Sync now" pressed during the automatic flush.
    const fetchMock = vi.fn().mockResolvedValue(itemResponse(201))
    vi.stubGlobal('fetch', fetchMock)

    const [first, second] = await Promise.all([flushQueue(), flushQueue()])

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(first.sent).toBe(1)
    expect(second).toEqual(first)
    expect(await listQueue()).toHaveLength(0)
  })

  it('stops and records the reason when the server refuses a queued edit', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await updateOrQueue(copy.id, MOVIE_ID, {
      formats: ['dvd'],
      hasPlaybackIssues: false,
      baseUpdatedAt: copy.updatedAt,
    })

    setOnline(true)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            detail: { code: 'STALE_EDIT', current: writtenItem },
          }),
          { status: 409 },
        ),
      ),
    )

    const result = await flushQueue()

    // The batch's own acceptance criterion: the offline edit does *not* win.
    expect(result.sent).toBe(0)
    const [entry] = await listQueue()
    expect(entry.error).toContain('changed while your edit was waiting')
  })

  it('leaves the queue alone and reports still-offline when there is no connection', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await updateOrQueue(copy.id, MOVIE_ID, { formats: ['dvd'], hasPlaybackIssues: false })

    const result = await flushQueue()

    expect(result.stillOffline).toBe(true)
    expect(result.sent).toBe(0)
    expect((await listQueue())[0].state).toBe('queued')
  })

  it('replays in the order the writes were made', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await addOrQueue({ movieId: MOVIE_ID, formats: ['dvd'], hasPlaybackIssues: false })
    await addOrQueue({ movieId: MOVIE_ID, formats: ['4k_uhd'], hasPlaybackIssues: false })

    setOnline(true)
    const fetchMock = vi.fn().mockResolvedValue(itemResponse(201))
    vi.stubGlobal('fetch', fetchMock)

    await flushQueue()

    const bodies = fetchMock.mock.calls.map(
      (call) => JSON.parse(String((call[1] as RequestInit).body)) as { formats: string[] },
    )
    // An edit that overtook the create it depends on would address an id the server has
    // never seen, so order is not cosmetic.
    expect(bodies.map((body) => body.formats[0])).toEqual(['dvd', '4k_uhd'])
  })
})

// Batch Z1 (`DECISIONS.md` #287). An add made from a TMDB search names the film by its TMDB
// id; the catalogue has no film id for it yet. `reconcile` gave up on those ("unknown"), so a
// lost answer stayed "never heard back" until the person discarded it.
describe('an add named by its TMDB id, a series id or a title', () => {
  const TMDB_ADD = { tmdbId: 1404, formats: ['blu_ray'], location: null, hasPlaybackIssues: false }

  function duplicateCheck(movieId: string | null) {
    return new Response(
      JSON.stringify({
        movieId,
        movieTitle: movieId ? 'Paper Kite' : null,
        isDuplicate: false,
        existingCopies: [],
        isUpgrade: false,
        bestFormatOwned: null,
      }),
    )
  }

  /** Queue the add, then lose the replay's answer, as a deploy restart does. */
  async function lostAdd(input: Parameters<typeof addOrQueue>[0]) {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await addOrQueue(input)
    setOnline(true)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })))
    await flushQueue()
    expect((await listQueue())[0].state).toBe('unconfirmed')
  }

  function methods(fetchMock: ReturnType<typeof vi.fn>): string[] {
    return fetchMock.mock.calls.map(([url, init]) => {
      const path = new URL(String(url), 'http://app.test').pathname
      return `${(init as RequestInit | undefined)?.method ?? 'GET'} ${path}`
    })
  }

  it('reads the film back by its TMDB id and settles when the add landed', async () => {
    await lostAdd(TMDB_ADD)
    const readBack = vi
      .fn()
      .mockResolvedValueOnce(duplicateCheck(MOVIE_ID))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ ...copy, formats: ['blu_ray'], location: null }])))
    vi.stubGlobal('fetch', readBack)

    const result = await flushQueue()

    expect(result.sent).toBe(1)
    expect(await listQueue()).toHaveLength(0)
    // Two reads and no POST: a second POST here is a second disc.
    expect(methods(readBack)).toEqual([
      'GET /api/v1/collection/duplicate-check',
      `GET /api/v1/movies/${MOVIE_ID}/copies`,
    ])
    expect(String(readBack.mock.calls[0][0])).toContain('tmdbId=1404')
  })

  it('returns it to queued when the catalogue has never heard of the film, and sends it then', async () => {
    await lostAdd(TMDB_ADD)
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(duplicateCheck(null))
      .mockResolvedValueOnce(itemResponse(201))
    vi.stubGlobal('fetch', fetchMock)

    const result = await flushQueue()

    expect(result.sent).toBe(1)
    expect(await listQueue()).toHaveLength(0)
    expect(methods(fetchMock)).toEqual(['GET /api/v1/collection/duplicate-check', 'POST /api/v1/collection'])
  })

  it('returns it to queued when the film is there but this disc is not', async () => {
    await lostAdd(TMDB_ADD)
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(duplicateCheck(MOVIE_ID))
      .mockResolvedValueOnce(new Response(JSON.stringify([])))
      // The resend loses its answer too; what matters here is that it came after both reads.
      .mockResolvedValueOnce(new Response('', { status: 503 }))
    vi.stubGlobal('fetch', fetchMock)

    await flushQueue()

    expect(methods(fetchMock)).toEqual([
      'GET /api/v1/collection/duplicate-check',
      `GET /api/v1/movies/${MOVIE_ID}/copies`,
      'POST /api/v1/collection',
    ])
  })

  it('leaves it unconfirmed when the read cannot be made, and sends nothing', async () => {
    await lostAdd(TMDB_ADD)
    const unreachable = droppedFetch()
    vi.stubGlobal('fetch', unreachable)

    const result = await flushQueue()

    expect(result.sent).toBe(0)
    expect((await listQueue())[0].state).toBe('unconfirmed')
    expect(methods(unreachable)).toEqual(['GET /api/v1/collection/duplicate-check'])
  })

  it('reads a series add back by its series id, and a title-only add by its title', async () => {
    for (const [input, query] of [
      [{ ...TMDB_ADD, tmdbId: undefined, tmdbTvId: 2316 }, 'tmdbTvId=2316'],
      [{ ...TMDB_ADD, tmdbId: undefined, title: 'Life on Earth' }, 'title=Life+on+Earth'],
    ] as const) {
      await clearQueue()
      await lostAdd(input)
      const readBack = vi
        .fn()
        .mockResolvedValueOnce(duplicateCheck(MOVIE_ID))
        .mockResolvedValueOnce(new Response(JSON.stringify([{ ...copy, formats: ['blu_ray'], location: null }])))
      vi.stubGlobal('fetch', readBack)

      expect((await flushQueue()).sent).toBe(1)
      expect(await listQueue()).toHaveLength(0)
      expect(String(readBack.mock.calls[0][0])).toContain(query)
    }
  })

  it('names the formats in the queue as the Archive does', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await addOrQueue({ ...TMDB_ADD, formats: ['4k_uhd', 'blu_ray'] })

    const [entry] = await listQueue()
    expect(entry.label).toBe('Add a disc (4K UHD + Blu-ray)')
  })
})

describe('a server that answers without being the application', () => {
  it('treats a 5xx on a write as unknown, not as a refusal', async () => {
    // `fetch` *resolves* for a 503, so this looked like an answer and the write was
    // being discarded. A gateway, a proxy or a container still booting all produce one,
    // and none of them can say whether the write was applied.
    setOnline(true)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })))

    await updateOrQueue(copy.id, MOVIE_ID, { formats: ['dvd'], hasPlaybackIssues: false })

    const [entry] = await listQueue()
    expect(entry).toBeDefined()
    expect(entry.state).toBe('unconfirmed')
  })

  it('still treats a 4xx as the application refusing', async () => {
    setOnline(true)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'nope' }), { status: 422 })),
    )

    // A refusal is a fact, not a thing to hold on to and replay later.
    await expect(
      updateOrQueue(copy.id, MOVIE_ID, { formats: ['dvd'], hasPlaybackIssues: false }),
    ).rejects.toThrow()
    expect(await listQueue()).toHaveLength(0)
  })
})

describe('signing out', () => {
  it('empties the queue, so an unsent write cannot fire under the next person', async () => {
    setOnline(false)
    vi.stubGlobal('fetch', offlineFetch())
    await deleteOrQueue(copy.id, MOVIE_ID)
    expect(await listQueue()).toHaveLength(1)

    await clearQueue()

    expect(await listQueue()).toHaveLength(0)
  })
})
