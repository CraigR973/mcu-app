import {
  apiErrorSchema,
  auditPageSchema,
  candidateListSchema,
  collectionCopiesSchema,
  collectionFacetsSchema,
  collectionItemSchema,
  duplicateCheckSchema,
  movieDetailSchema,
  moviePageSchema,
  searchResponseSchema,
  tmdbSearchResponseSchema,
  trashPageSchema,
  watchLogEntrySchema,
  watchLogPageSchema,
  type AuditPage,
  type CandidateList,
  type CollectionCopy,
  type CollectionFacets,
  type CollectionItem,
  type Condition,
  type DuplicateCheck,
  type DuplicateReason,
  type MovieDetail,
  type MoviePage,
  type SearchResponse,
  type TmdbSearchResponse,
  type TrashPage,
  type WatchLogEntry,
  type WatchLogPage,
} from '@mcu/shared'
import { z, type ZodType } from 'zod'

import { authFetch } from './auth-tokens'

export type {
  AuditEntry,
  AuditPage,
  Candidate,
  CandidateList,
  CollectionCopy,
  CollectionFacets,
  CollectionItem,
  Condition,
  DecadeFacet,
  DuplicateCheck,
  DuplicateReason,
  ExistingCopy,
  FormatCode,
  MovieDetail,
  MovieListItem,
  MovieLocation,
  MoviePage,
  SearchResponse,
  SectionFacet,
  ShelfFacet,
  TmdbSearchResult,
  TrashItem,
  TrashPage,
  WatchLogEntry,
  WatchLogPage,
} from '@mcu/shared'

/**
 * The server answered, and the answer was no.
 *
 * Distinguished from {@link NetworkError} because the two demand opposite handling: a
 * refusal is a fact the person can act on, while silence is a question that has to be
 * resolved before anything is reported.
 */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/**
 * The request did not produce an answer.
 *
 * `mayHaveLanded` is the field the whole offline queue turns on. Only a request the
 * browser refused to make while reporting itself offline *definitely* never reached the
 * server; anything else — a connection that dropped a millisecond after the bytes went
 * out — might have been applied. Guessing "it never landed" and re-sending creates
 * duplicate discs and silently reverts newer edits, so the unknown case is never
 * retried on its own (`DECISIONS.md` #43).
 */
export class NetworkError extends Error {
  constructor(
    message: string,
    readonly mayHaveLanded: boolean,
    options?: { cause?: unknown },
  ) {
    super(message, options)
    this.name = 'NetworkError'
  }
}

/**
 * `authFetch`, with a transport failure turned into a {@link NetworkError}.
 *
 * `fetch` rejects with a bare `TypeError` for everything from "you are on a train" to
 * "DNS is broken", and a `TypeError` reaching a mutation's `onError` is indistinguishable
 * from a bug in our own code. Classifying it here is what lets every write path decide
 * correctly without repeating the reasoning.
 */
export async function send(path: string, options: RequestInit = {}): Promise<Response> {
  let response: Response
  try {
    response = await authFetch(path, options)
  } catch (cause) {
    // `navigator.onLine === false` is the one case the browser is authoritative about:
    // it did not attempt the request, so the server cannot hold it.
    const offline = typeof navigator !== 'undefined' && !navigator.onLine
    throw new NetworkError(
      offline ? 'You are offline.' : 'Could not reach the server.',
      !offline,
      { cause },
    )
  }

  // A 5xx or a 408 is **not** the application answering. A gateway, a proxy, a captive
  // portal and a container that is still booting all produce one, and none of them can
  // say whether the write was applied — which is the definition of the unknown case.
  //
  // Found by driving the app with its API switched off: `fetch` *resolves* for a 503, so
  // a write that never reached the application was being classified as a refusal and
  // thrown away. An edit made on a train behind a captive portal would have vanished
  // silently (`DECISIONS.md` #45).
  if (response.status >= 500 || response.status === 408) {
    throw new NetworkError('The server did not answer.', true)
  }
  return response
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    const parsed = apiErrorSchema.parse(body)
    return parsed.error ?? parsed.detail ?? `HTTP ${response.status}`
  } catch {
    // A proxy or network edge can return HTML. The status is still useful to the caller.
  }
  return `HTTP ${response.status}`
}

async function parseResponse<T>(response: Response, schema: ZodType<T>): Promise<T> {
  if (!response.ok) throw new Error(await errorMessage(response))
  const body: unknown = await response.json()
  return schema.parse(body)
}

/** As `parseResponse`, but a refused request raises a typed {@link ApiError}. */
async function parseOrThrowApiError<T>(response: Response, schema: ZodType<T>): Promise<T> {
  if (!response.ok) {
    let detail: unknown
    try {
      detail = ((await response.clone().json()) as { detail?: unknown }).detail
    } catch {
      /* not JSON — the status is still the answer */
    }
    throw new ApiError(await errorMessage(response), response.status, detail)
  }
  const body: unknown = await response.json()
  return schema.parse(body)
}

export interface MovieFilters {
  genreId?: number
  year?: number
  format?: string
  section?: string
  shelf?: string
  /** First year of the earliest decade to include — 1940 means "1940s or later". */
  decadeFrom?: number
  /** First year of the latest decade to include — 1940 means "up to and including 1949". */
  decadeTo?: number
  minRating?: number
  watched?: boolean
  sort?: 'title' | 'year' | 'rating'
  order?: 'asc' | 'desc'
}

export async function fetchMovies(
  filters: MovieFilters = {},
  page = 1,
  perPage = 60,
): Promise<MoviePage> {
  const params = new URLSearchParams({ page: String(page), perPage: String(perPage) })
  if (filters.genreId) params.set('genreId', String(filters.genreId))
  if (filters.year) params.set('year', String(filters.year))
  if (filters.format) params.set('format', filters.format)
  if (filters.section) params.set('section', filters.section)
  if (filters.shelf) params.set('shelf', filters.shelf)
  if (filters.decadeFrom) params.set('decadeFrom', String(filters.decadeFrom))
  if (filters.decadeTo) params.set('decadeTo', String(filters.decadeTo))
  // `!= null` rather than truthiness: a minimum rating of 0 and `watched: false` are
  // both meaningful filters that a truthiness check would silently drop.
  if (filters.minRating != null) params.set('minRating', String(filters.minRating))
  if (filters.watched != null) params.set('watched', String(filters.watched))
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.order) params.set('order', filters.order)

  return parseResponse(await authFetch(`/movies?${params}`), moviePageSchema)
}

export async function fetchFacets(): Promise<CollectionFacets> {
  return parseResponse(await authFetch('/collection/facets'), collectionFacetsSchema)
}

export interface LogWatchInput {
  movieId: string
  watchedAt?: string
  isRewatch?: boolean
  personalRating?: number | null
  review?: string | null
}

export async function logWatch(input: LogWatchInput): Promise<WatchLogEntry> {
  return parseResponse(
    await authFetch('/watch-log', { method: 'POST', body: JSON.stringify(input) }),
    watchLogEntrySchema,
  )
}

export async function fetchWatches(movieId?: string, perPage = 50): Promise<WatchLogPage> {
  const params = new URLSearchParams({ perPage: String(perPage) })
  if (movieId) params.set('movieId', movieId)
  return parseResponse(await authFetch(`/watch-log?${params}`), watchLogPageSchema)
}

export async function deleteWatch(entryId: string): Promise<void> {
  const response = await authFetch(`/watch-log/${entryId}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await errorMessage(response))
}

/** §3.7's half-star scale, for a star control that must not invent its own steps. */
export const RATING_STEPS = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5] as const

/** The TMDB-rating thresholds the filter bar offers. */
export const MIN_RATING_OPTIONS = [9, 8, 7, 6, 5] as const

export async function fetchMovie(id: string): Promise<MovieDetail> {
  return parseResponse(await authFetch(`/movies/${id}`), movieDetailSchema)
}

export async function fetchCopies(movieId: string): Promise<CollectionCopy[]> {
  return parseResponse(await authFetch(`/movies/${movieId}/copies`), collectionCopiesSchema)
}

export async function fetchSearch(q: string, limit = 20): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return parseResponse(await authFetch(`/search?${params}`), searchResponseSchema)
}

export async function fetchCandidates(movieId: string, query?: string): Promise<CandidateList> {
  const params = new URLSearchParams()
  if (query) params.set('query', query)
  const suffix = params.size ? `?${params}` : ''
  return parseResponse(
    await authFetch(`/movies/${movieId}/candidates${suffix}`),
    candidateListSchema,
  )
}

export async function identifyMovie(movieId: string, tmdbId: number): Promise<MovieDetail> {
  return parseResponse(
    await authFetch(`/movies/${movieId}/identify`, {
      method: 'POST',
      body: JSON.stringify({ tmdbId }),
    }),
    movieDetailSchema,
  )
}

export function backdropUrl(path: string | null, size = 'w1280'): string {
  if (!path) return ''
  return `https://image.tmdb.org/t/p/${size}${path}`
}

export function posterUrl(path: string | null, size = 'w342'): string {
  if (!path) return '/placeholder-poster.svg'
  return `https://image.tmdb.org/t/p/${size}${path}`
}

export const TMDB_GENRES: { id: number; name: string }[] = [
  { id: 28, name: 'Action' },
  { id: 12, name: 'Adventure' },
  { id: 16, name: 'Animation' },
  { id: 35, name: 'Comedy' },
  { id: 80, name: 'Crime' },
  { id: 99, name: 'Documentary' },
  { id: 18, name: 'Drama' },
  { id: 10751, name: 'Family' },
  { id: 14, name: 'Fantasy' },
  { id: 36, name: 'History' },
  { id: 27, name: 'Horror' },
  { id: 10402, name: 'Music' },
  { id: 9648, name: 'Mystery' },
  { id: 10749, name: 'Romance' },
  { id: 878, name: 'Science Fiction' },
  { id: 53, name: 'Thriller' },
  { id: 10752, name: 'War' },
  { id: 37, name: 'Western' },
]

export const FORMATS = [
  { value: '4k_uhd', label: '4K UHD' },
  { value: 'blu_ray', label: 'Blu-ray' },
  { value: 'dvd', label: 'DVD' },
  { value: 'download', label: 'Digital' },
] as const

export const FORMAT_COLORS: Record<string, string> = {
  '4k_uhd': 'bg-sky-600 text-white',
  'blu_ray': 'bg-indigo-600 text-white',
  'dvd': 'bg-slate-500 text-white',
  'download': 'bg-emerald-700 text-white',
}

export function formatLabel(value: string | null): string | null {
  if (!value) return null
  return FORMATS.find((format) => format.value === value)?.label ?? value.replaceAll('_', ' ')
}

// ---------------------------------------------------------------------------
// Write surface (Batch 7) — §3.1, §3.2, §3.5, §3.11
//
// Admin-only. Every response is parsed through `@mcu/shared` like the read surface;
// nothing here casts.
// ---------------------------------------------------------------------------

/** The condition vocabulary, in the order a disc degrades. */
export const CONDITIONS = [
  { value: 'new', label: 'New' },
  { value: 'like_new', label: 'Like new' },
  { value: 'good', label: 'Good' },
  { value: 'acceptable', label: 'Acceptable' },
  { value: 'damaged', label: 'Damaged' },
] as const

export function conditionLabel(value: string | null): string | null {
  if (!value) return null
  return CONDITIONS.find((entry) => entry.value === value)?.label ?? value.replaceAll('_', ' ')
}

/** The editable field set, exactly as `PUT`/`POST` accept it. Kept as one interface so
 *  the add form and the edit form cannot drift into sending different shapes. */
export interface CollectionItemFields {
  formats: string[]
  location?: string | null
  section?: string | null
  shelf?: string | null
  subCategory?: string | null
  notes?: string | null
  condition?: Condition | null
  hasPlaybackIssues: boolean
  playbackNotes?: string | null
  purchasePrice?: string | null
  purchaseSource?: string | null
  purchaseDate?: string | null
}

/** Thrown when the API refuses an unconfirmed duplicate, carrying what the §3.5 prompt
 *  needs. A plain `Error` would reduce the 409 body to a string and lose the copies. */
export class DuplicateItemError extends Error {
  constructor(readonly duplicate: DuplicateCheck) {
    super('This film is already in the collection')
    this.name = 'DuplicateItemError'
  }
}

export async function checkDuplicate(
  film: { movieId: string } | { tmdbId: number },
  formats: string[],
): Promise<DuplicateCheck> {
  const params = new URLSearchParams()
  if ('movieId' in film) params.set('movieId', film.movieId)
  else params.set('tmdbId', String(film.tmdbId))
  for (const format of formats) params.append('format', format)
  return parseResponse(await authFetch(`/collection/duplicate-check?${params}`), duplicateCheckSchema)
}

export type AddCollectionItemInput = CollectionItemFields & {
  movieId?: string
  tmdbId?: number
  confirmDuplicate?: DuplicateReason
}

export async function addCollectionItem(
  input: AddCollectionItemInput,
): Promise<CollectionItem> {
  const response = await send('/collection', { method: 'POST', body: JSON.stringify(input) })
  if (response.status === 409) {
    const body: unknown = await response.json()
    const parsed = z.object({ detail: duplicateCheckSchema }).safeParse(body)
    if (parsed.success) throw new DuplicateItemError(parsed.data.detail)
    throw new Error('This film is already in the collection')
  }
  return parseOrThrowApiError(response, collectionItemSchema)
}

/** Thrown when a queued edit is refused because the disc changed after it was made. */
export class StaleEditError extends Error {
  constructor(readonly current: CollectionItem) {
    super('This disc changed after your edit was made.')
    this.name = 'StaleEditError'
  }
}

export type UpdateCollectionItemInput = CollectionItemFields & {
  /**
   * The `updatedAt` this edit was made against.
   *
   * Sent by anything that may have been composed a while ago — which offline is
   * everything. Without it the server has no way to refuse a stale write, and a queued
   * edit flushed after someone else moved the disc would silently win.
   */
  baseUpdatedAt?: string
}

export async function updateCollectionItem(
  itemId: string,
  input: UpdateCollectionItemInput,
): Promise<CollectionItem> {
  const response = await send(`/collection/${itemId}`, {
    method: 'PUT',
    body: JSON.stringify(input),
  })
  if (response.status === 409) {
    const body: unknown = await response.json()
    const parsed = z
      .object({ detail: z.object({ code: z.literal('STALE_EDIT'), current: collectionItemSchema }) })
      .safeParse(body)
    if (parsed.success) throw new StaleEditError(parsed.data.detail.current)
  }
  return parseOrThrowApiError(response, collectionItemSchema)
}

export async function deleteCollectionItem(itemId: string): Promise<CollectionItem> {
  return parseOrThrowApiError(
    await send(`/collection/${itemId}`, { method: 'DELETE' }),
    collectionItemSchema,
  )
}

export async function fetchTrash(): Promise<TrashPage> {
  return parseResponse(await authFetch('/trash?perPage=200'), trashPageSchema)
}

export async function restoreCollectionItem(itemId: string): Promise<CollectionItem> {
  return parseResponse(
    await authFetch(`/trash/collection_items/${itemId}/restore`, { method: 'POST' }),
    collectionItemSchema,
  )
}

/** The audit log. `movieId` is what the detail page's history panel passes — it resolves
 *  to every one of that film's discs, deleted ones included. */
export async function fetchAudit(
  filter: { movieId?: string; targetId?: string } = {},
  perPage = 50,
): Promise<AuditPage> {
  const params = new URLSearchParams({ perPage: String(perPage) })
  if (filter.movieId) params.set('movieId', filter.movieId)
  if (filter.targetId) params.set('targetId', filter.targetId)
  return parseResponse(await authFetch(`/admin/audit?${params}`), auditPageSchema)
}

export async function searchTmdb(q: string): Promise<TmdbSearchResponse> {
  const params = new URLSearchParams({ q })
  return parseResponse(await authFetch(`/tmdb/search?${params}`), tmdbSearchResponseSchema)
}
