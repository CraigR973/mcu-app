import {
  activitySchema,
  apiErrorSchema,
  auditPageSchema,
  boxSetDetailSchema,
  calendarIngestSchema,
  calendarListSchema,
  calendarMonthSchema,
  calendarSubscriptionSchema,
  boxSetListSchema,
  candidateListSchema,
  collectionCopiesSchema,
  collectionFacetsSchema,
  collectionItemSchema,
  completionInsightsSchema,
  completionRefreshSchema,
  completionSetDetailSchema,
  duplicateCheckSchema,
  movieDetailSchema,
  moviePageSchema,
  newReleaseListSchema,
  builtInScraperListSchema,
  retailerListSchema,
  retailerSchema,
  retailerSeedSchema,
  scraperTestSchema,
  scrapeRunSchema,
  recommendationListSchema,
  streamingSchema,
  profileResponseSchema,
  loanListSchema,
  loanSchema,
  purgePreviewSchema,
  searchResponseSchema,
  smartCollectionListSchema,
  statsSchema,
  smartCollectionResultsSchema,
  smartCollectionSchema,
  tmdbSearchResponseSchema,
  trashListSchema,
  trashPageSchema,
  wantedItemSchema,
  wantedListSchema,
  watchLogEntrySchema,
  watchLogPageSchema,
  type Activity,
  type AuditPage,
  type BoxSetDetail,
  type BoxSetList,
  type CalendarIngest,
  type CalendarListing,
  type CalendarMonth,
  type CalendarSubscription,
  type CandidateList,
  type CollectionCopy,
  type CollectionFacets,
  type CollectionItem,
  type CompletionInsights,
  type CompletionRefresh,
  type CompletionSetDetail,
  type CompletionSetType,
  type Condition,
  type DuplicateCheck,
  type DuplicateReason,
  type Loan,
  type LoanList,
  type PurgePreview,
  type MovieDetail,
  type MoviePage,
  type NewReleaseList,
  type OfferKind,
  type RecommendationList,
  type RetailerList,
  type RetailerRow,
  type BuiltInScraperList,
  type RetailerSeed,
  type ScrapeFrequency,
  type ScrapeRun,
  type ScraperTest,
  type ScraperType,
  type Streaming,
  type ProfileResponse,
  type SearchResponse,
  type SmartCollection,
  type SmartCollectionFilters,
  type SmartCollectionList,
  type SmartCollectionResults,
  type Stats,
  type TmdbSearchResponse,
  type TrashList,
  type TrashPage,
  type WantedItem,
  type WantedList,
  type TrashTable,
  type WatchLogEntry,
  type WatchLogPage,
} from '@mcu/shared'
import { z, type ZodType } from 'zod'

import { authFetch } from './auth-tokens'

export type {
  Activity,
  ActivityEvent,
  ActivityKind,
  AuditEntry,
  AuditPage,
  BoxSet,
  BoxSetDetail,
  BoxSetList,
  BoxSetMember,
  CalendarEntry,
  CalendarIngest,
  CalendarListing,
  CalendarMonth,
  CalendarSubscription,
  Candidate,
  ReleaseType,
  CandidateList,
  CollectionCopy,
  CollectionFacets,
  CollectionItem,
  CompletionFilm,
  CompletionInsights,
  CompletionSet,
  CompletionSetDetail,
  CompletionSetType,
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
  NewRelease,
  NewReleaseList,
  OfferKind,
  OwnershipState,
  Recommendation,
  RecommendationList,
  BuiltInScraper,
  BuiltInScraperList,
  RetailerList,
  RetailerRow,
  ScrapeFrequency,
  ScrapeOutcome,
  ScrapeRun,
  ScraperTest,
  ScraperType,
  Streaming,
  StreamingOffer,
  SearchResponse,
  SectionFacet,
  ShelfFacet,
  SmartCollection,
  SmartCollectionFilters,
  SmartCollectionIcon,
  SmartCollectionList,
  SmartCollectionResults,
  SpendPoint,
  Stats,
  TmdbSearchResult,
  WatchedFilm,
  Loan,
  LoanList,
  PurgePreview,
  TrashCount,
  TrashItem,
  TrashList,
  TrashPage,
  TrashRow,
  TrashTable,
  WantedItem,
  WantedList,
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
export interface AuditFilter {
  movieId?: string
  targetId?: string
  /** Batch 15 (§13.6). Who and when are the two questions a person brings to an audit
   *  log, and neither was answerable before. */
  actionType?: string
  actorId?: string
  since?: string
  until?: string
  perPage?: number
}

export async function fetchAudit(
  filter: AuditFilter = {},
  perPage = 50,
): Promise<AuditPage> {
  const params = new URLSearchParams({ perPage: String(filter.perPage ?? perPage) })
  if (filter.movieId) params.set('movieId', filter.movieId)
  if (filter.targetId) params.set('targetId', filter.targetId)
  if (filter.actionType) params.set('actionType', filter.actionType)
  if (filter.actorId) params.set('actorId', filter.actorId)
  if (filter.since) params.set('since', filter.since)
  if (filter.until) params.set('until', filter.until)
  return parseResponse(await authFetch(`/admin/audit?${params}`), auditPageSchema)
}

/** Mark the setup wizard finished. Idempotent; the API keeps the first timestamp. */
export async function completeOnboarding(): Promise<ProfileResponse> {
  return parseResponse(
    await authFetch('/auth/onboarding/complete', { method: 'POST' }),
    profileResponseSchema,
  )
}

export async function searchTmdb(q: string): Promise<TmdbSearchResponse> {
  const params = new URLSearchParams({ q })
  return parseResponse(await authFetch(`/tmdb/search?${params}`), tmdbSearchResponseSchema)
}

// ---------------------------------------------------------------------------
// Box sets and smart collections (Batch 12) — §11.3, §11.4, §11.5
// ---------------------------------------------------------------------------

export async function fetchBoxSets(): Promise<BoxSetList> {
  return parseResponse(await authFetch('/box-sets'), boxSetListSchema)
}

export async function fetchBoxSet(id: string): Promise<BoxSetDetail> {
  return parseResponse(await authFetch(`/box-sets/${id}`), boxSetDetailSchema)
}

export interface BoxSetInput {
  name: string
  label?: string | null
  volumeNumber?: number | null
  seriesId?: string | null
  expectedCount?: number | null
  posterUrl?: string | null
  notes?: string | null
}

export async function createBoxSet(
  input: BoxSetInput & { itemIds?: string[] },
): Promise<BoxSetDetail> {
  return parseOrThrowApiError(
    await authFetch('/box-sets', { method: 'POST', body: JSON.stringify(input) }),
    boxSetDetailSchema,
  )
}

export async function updateBoxSet(id: string, input: BoxSetInput): Promise<BoxSetDetail> {
  return parseOrThrowApiError(
    await authFetch(`/box-sets/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
    boxSetDetailSchema,
  )
}

export async function deleteBoxSet(id: string): Promise<void> {
  const response = await authFetch(`/box-sets/${id}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await errorMessage(response))
}

export async function addBoxSetItem(
  id: string,
  collectionItemId: string,
  discNumber?: number | null,
): Promise<BoxSetDetail> {
  return parseOrThrowApiError(
    await authFetch(`/box-sets/${id}/items`, {
      method: 'POST',
      body: JSON.stringify({ collectionItemId, discNumber: discNumber ?? null }),
    }),
    boxSetDetailSchema,
  )
}

export async function removeBoxSetItem(
  id: string,
  collectionItemId: string,
): Promise<BoxSetDetail> {
  return parseOrThrowApiError(
    await authFetch(`/box-sets/${id}/items/${collectionItemId}`, { method: 'DELETE' }),
    boxSetDetailSchema,
  )
}

/**
 * How a box set reads in one line — §11.4's "3 of 4".
 *
 * Three-valued on purpose. A set whose expected size nobody recorded is *unmeasured*,
 * not incomplete, and saying "3 of 0" or "incomplete" would put a permanent red mark
 * against every set an admin never filled in.
 */
export function completionLabel(set: { ownedCount: number; expectedCount: number | null }): string {
  if (set.expectedCount === null) {
    return `${set.ownedCount} ${set.ownedCount === 1 ? 'disc' : 'discs'}`
  }
  return `${set.ownedCount} of ${set.expectedCount}`
}

export async function fetchSmartCollections(pinned?: boolean): Promise<SmartCollectionList> {
  const suffix = pinned === undefined ? '' : `?pinned=${String(pinned)}`
  return parseResponse(await authFetch(`/smart-collections${suffix}`), smartCollectionListSchema)
}

export interface SmartCollectionInput {
  name: string
  icon: SmartCollection['icon']
  /** Partial: the API fills every unstated field with `null` and stores only what is
   *  constrained, so a form need not send nine keys to save one. */
  filters: Partial<Record<keyof SmartCollectionFilters, unknown>>
  sortBy: SmartCollection['sortBy']
  sortOrder: SmartCollection['sortOrder']
  isPinned: boolean
  displayOrder?: number
}

export async function createSmartCollection(
  input: SmartCollectionInput,
): Promise<SmartCollection> {
  return parseOrThrowApiError(
    await authFetch('/smart-collections', { method: 'POST', body: JSON.stringify(input) }),
    smartCollectionSchema,
  )
}

export async function updateSmartCollection(
  id: string,
  input: SmartCollectionInput,
): Promise<SmartCollection> {
  return parseOrThrowApiError(
    await authFetch(`/smart-collections/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
    smartCollectionSchema,
  )
}

export async function deleteSmartCollection(id: string): Promise<void> {
  const response = await authFetch(`/smart-collections/${id}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await errorMessage(response))
}

export async function fetchSmartCollectionResults(
  id: string,
  perPage = 2000,
): Promise<SmartCollectionResults> {
  return parseResponse(
    await authFetch(`/smart-collections/${id}/results?perPage=${String(perPage)}`),
    smartCollectionResultsSchema,
  )
}

/**
 * A saved collection's filters as the `MovieFilters` the filter bar speaks.
 *
 * The two vocabularies are deliberately the same, so this is a null-stripping cast
 * rather than a translation — and it is what lets a collection's own results page reuse
 * the collection grid instead of describing the same films a second way.
 */
export function filtersToMovieFilters(filters: SmartCollectionFilters): MovieFilters {
  const out: MovieFilters = {}
  if (filters.genreId !== null) out.genreId = filters.genreId
  if (filters.year !== null) out.year = filters.year
  if (filters.format !== null) out.format = filters.format
  if (filters.section !== null) out.section = filters.section
  if (filters.shelf !== null) out.shelf = filters.shelf
  if (filters.decadeFrom !== null) out.decadeFrom = filters.decadeFrom
  if (filters.decadeTo !== null) out.decadeTo = filters.decadeTo
  if (filters.minRating !== null) out.minRating = filters.minRating
  if (filters.watched !== null) out.watched = filters.watched
  return out
}

/** A human sentence for what a saved collection selects, for the sidebar and the cards. */
export function describeFilters(filters: SmartCollectionFilters): string {
  const parts: string[] = []
  if (filters.watched !== null) parts.push(filters.watched ? 'watched' : 'unwatched')
  if (filters.format !== null) parts.push(formatLabel(filters.format) ?? filters.format)
  if (filters.genreId !== null) {
    parts.push(TMDB_GENRES.find((g) => g.id === filters.genreId)?.name ?? 'a genre')
  }
  if (filters.decadeFrom !== null || filters.decadeTo !== null) {
    const from = filters.decadeFrom
    const to = filters.decadeTo
    if (from !== null && to !== null && from === to) parts.push(`${String(from)}s`)
    else if (from !== null && to !== null) parts.push(`${String(from)}s–${String(to)}s`)
    else if (from !== null) parts.push(`${String(from)}s onwards`)
    else if (to !== null) parts.push(`up to the ${String(to)}s`)
  }
  if (filters.year !== null) parts.push(String(filters.year))
  if (filters.minRating !== null) parts.push(`rated ${String(filters.minRating)}+`)
  if (filters.section !== null) parts.push(filters.shelf !== null ? `${filters.section} ${filters.shelf}` : filters.section)
  else if (filters.shelf !== null) parts.push(`${filters.shelf} shelf`)
  return parts.length === 0 ? 'Everything in the collection' : parts.join(' · ')
}

// ---------------------------------------------------------------------------
// Completion insights (Batch 13) — §11.2
// ---------------------------------------------------------------------------

export async function fetchCompletionInsights(setType?: string): Promise<CompletionInsights> {
  const suffix = setType ? `?setType=${encodeURIComponent(setType)}` : ''
  return parseResponse(await authFetch(`/insights/completion${suffix}`), completionInsightsSchema)
}

export async function fetchCompletionSet(id: string): Promise<CompletionSetDetail> {
  return parseResponse(
    await authFetch(`/insights/completion/${id}`),
    completionSetDetailSchema,
  )
}

/**
 * Rebuild the sets from TMDB. Admin-only, and slow — one API call per set.
 *
 * "Weekly" is not implemented in the app: scheduling is a hosting concern this project
 * keeps explicit, so this button and `src/scripts/refresh_completion_sets.py` are what a
 * schedule would call once someone wires one up.
 */
export async function refreshCompletionSets(dryRun = false): Promise<CompletionRefresh> {
  return parseOrThrowApiError(
    await authFetch(`/insights/completion/refresh?dryRun=${String(dryRun)}`, {
      method: 'POST',
    }),
    completionRefreshSchema,
  )
}

/** How a completion set reads in one line — "12 of 61". */
export function completionCountLabel(set: {
  ownedCount: number
  totalCount: number
}): string {
  return `${set.ownedCount} of ${set.totalCount}`
}

/** The set's kind, as a person would say it. */
export function setTypeLabel(setType: CompletionSetType): string {
  const labels: Record<CompletionSetType, string> = {
    director: 'Director',
    actor: 'Actor',
    franchise: 'Franchise',
    box_set: 'Box set',
    award: 'Award',
    curated_list: 'List',
  }
  return labels[setType]
}

// ---------------------------------------------------------------------------
// Stats, activity and export (Batch 14) — §13.1–13.4
// ---------------------------------------------------------------------------

export async function fetchStats(): Promise<Stats> {
  return parseResponse(await authFetch('/collection/stats'), statsSchema)
}

export async function fetchActivity(limit = 20): Promise<Activity> {
  return parseResponse(await authFetch(`/activity?limit=${String(limit)}`), activitySchema)
}

/**
 * Download an export, with the token in the header where it belongs.
 *
 * **Not a plain `<a href>`.** A link cannot carry an `Authorization` header, so the only
 * way to make one work is to put the token in the query string — where it lands in server
 * logs, browser history and any `Referer` the page emits. The file is a few hundred KB for
 * 1,857 rows, so holding it as a blob costs nothing and keeps the credential out of the URL.
 *
 * The object URL is revoked immediately: Chrome keeps the blob alive until the download
 * commits, and leaving it attached leaks the whole file for the life of the tab.
 */
export async function downloadExport(format: 'csv' | 'json' | 'html'): Promise<void> {
  const query = format === 'html' ? '?download=true' : ''
  const response = await authFetch(`/export/collection.${format}${query}`)
  if (!response.ok) throw new Error(await errorMessage(response))

  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  try {
    const link = document.createElement('a')
    link.href = url
    link.download = filenameFrom(response) ?? `mcu-collection.${format}`
    document.body.appendChild(link)
    link.click()
    link.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
}

/** The name the server chose, so the file on disk matches what the API called it. */
function filenameFrom(response: Response): string | null {
  const header = response.headers.get('content-disposition')
  const match = header ? /filename="([^"]+)"/.exec(header) : null
  return match ? match[1] : null
}

/** Open the printable view in a new tab — §13.4's route to a PDF is the print dialog. */
export async function openPrintableCollection(): Promise<void> {
  const response = await authFetch('/export/collection.html')
  if (!response.ok) throw new Error(await errorMessage(response))
  const url = URL.createObjectURL(await response.blob())
  window.open(url, '_blank', 'noopener')
  // Not revoked immediately: the new tab has not fetched it yet. A minute is far longer
  // than the load needs and short enough that the blob does not outlive the session.
  setTimeout(() => { URL.revokeObjectURL(url) }, 60_000)
}

/** Integer pence as money, for the spend chart's axis and captions. */
export function poundsFromCents(cents: number): string {
  return `£${(cents / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

// ---------------------------------------------------------------------------
// Trash, purge and lending (Batch 15) — §13.5, §12.5
// ---------------------------------------------------------------------------

export async function fetchTrashTable(table: TrashTable, page = 1): Promise<TrashList> {
  return parseResponse(
    await authFetch(`/trash/all?table=${table}&page=${String(page)}&perPage=100`),
    trashListSchema,
  )
}

export async function restoreTrashRow(table: TrashTable, id: string): Promise<void> {
  const response = await authFetch(`/trash/${table}/${id}/restore-row`, { method: 'POST' })
  if (!response.ok) throw new Error(await errorMessage(response))
}

/**
 * **Irreversible.** Destroys the row.
 *
 * Named `destroy` rather than `delete` on purpose: everything else in this file called
 * "delete" is a soft delete that the trash undoes, and one word for both is how the wrong
 * one gets called.
 */
export async function destroyTrashRow(table: TrashTable, id: string): Promise<void> {
  const response = await authFetch(`/trash/${table}/${id}/permanent`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await errorMessage(response))
}

/** Dry by default, matching the endpoint — the destructive call is the one you ask for. */
export async function purgeTrash(table: TrashTable, dryRun = true): Promise<PurgePreview> {
  return parseOrThrowApiError(
    await authFetch(`/trash/purge?table=${table}&dryRun=${String(dryRun)}`, {
      method: 'POST',
    }),
    purgePreviewSchema,
  )
}

export const TRASH_TABLE_LABELS: Record<TrashTable, string> = {
  collection_items: 'Discs',
  watch_log: 'Watches',
  movies: 'Films',
  box_sets: 'Box sets',
  wanted_list: 'Wanted',
  retailers: 'Retailers',
}

export async function fetchLoans(openOnly = false): Promise<LoanList> {
  return parseResponse(
    await authFetch(`/loans?openOnly=${String(openOnly)}`),
    loanListSchema,
  )
}

export interface LendInput {
  collectionItemId: string
  borrowerName: string
  lentDate?: string
  dueDate?: string | null
  notes?: string | null
}

export async function lendDisc(input: LendInput): Promise<Loan> {
  return parseOrThrowApiError(
    await authFetch('/loans', { method: 'POST', body: JSON.stringify(input) }),
    loanSchema,
  )
}

export async function returnLoan(id: string, returnedDate?: string): Promise<Loan> {
  return parseOrThrowApiError(
    await authFetch(`/loans/${id}/return`, {
      method: 'PUT',
      body: JSON.stringify(returnedDate ? { returnedDate } : {}),
    }),
    loanSchema,
  )
}

/** How a loan's timing reads in one line. */
export function loanDueLabel(loan: {
  isOverdue: boolean
  daysUntilDue: number | null
  returnedDate: string | null
}): string {
  if (loan.returnedDate) return `returned ${loan.returnedDate}`
  if (loan.daysUntilDue === null) return 'no due date'
  if (loan.isOverdue) {
    const days = Math.abs(loan.daysUntilDue)
    return `${String(days)} day${days === 1 ? '' : 's'} overdue`
  }
  if (loan.daysUntilDue === 0) return 'due today'
  return `due in ${String(loan.daysUntilDue)} days`
}

// ---------------------------------------------------------------------------
// Streaming and recommendations (Batch 16) — §7.1, §7.2
// ---------------------------------------------------------------------------

export async function fetchStreaming(movieId: string, region?: string): Promise<Streaming> {
  const suffix = region ? `?region=${encodeURIComponent(region)}` : ''
  return parseResponse(
    await authFetch(`/movies/${movieId}/streaming${suffix}`),
    streamingSchema,
  )
}

export async function fetchRecommendations(movieId: string): Promise<RecommendationList> {
  return parseResponse(
    await authFetch(`/movies/${movieId}/recommendations`),
    recommendationListSchema,
  )
}

export async function fetchNewReleases(): Promise<NewReleaseList> {
  return parseResponse(await authFetch('/discover/new-releases'), newReleaseListSchema)
}

/** How each offer kind reads. TMDB's own three buckets, in a person's words. */
export const OFFER_KIND_LABELS: Record<OfferKind, string> = {
  flatrate: 'Streaming',
  rent: 'Rent',
  buy: 'Buy',
}

/** A TMDB provider logo. Same CDN as the posters, so no new CSP origin is needed. */
export function providerLogoUrl(path: string | null, size = 'w45'): string {
  if (!path) return '/placeholder-poster.svg'
  return `https://image.tmdb.org/t/p/${size}${path}`
}

// ---------------------------------------------------------------------------
// Release calendar and iCal feed (Batch 17) — §7.3, §7.4
// ---------------------------------------------------------------------------

export async function fetchCalendar(days = 120): Promise<CalendarListing> {
  return parseResponse(await authFetch(`/calendar?days=${String(days)}`), calendarListSchema)
}

export async function fetchCalendarMonth(month: string): Promise<CalendarMonth> {
  return parseResponse(
    await authFetch(`/calendar/month?month=${encodeURIComponent(month)}`),
    calendarMonthSchema,
  )
}

export async function subscribeToCalendar(): Promise<CalendarSubscription> {
  return parseOrThrowApiError(
    await authFetch('/calendar/subscribe', { method: 'POST' }),
    calendarSubscriptionSchema,
  )
}

export async function ingestCalendar(dryRun = false): Promise<CalendarIngest> {
  return parseOrThrowApiError(
    await authFetch(`/calendar/ingest?dryRun=${String(dryRun)}`, { method: 'POST' }),
    calendarIngestSchema,
  )
}

/**
 * The absolute feed URL, composed here rather than server-side.
 *
 * The API deliberately returns a path: deriving an origin from the request's `Host`
 * header would reflect an attacker-controlled value into a subscription link, and
 * configuring one would be a new Railway variable. `VITE_API_URL` is the one place the
 * origin is known for certain — it is what every other request already goes to.
 */
export function calendarFeedUrl(path: string): string {
  const base = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '')
  if (base) return `${base}${path}`
  // Dev, where the app is served from the same origin the vite proxy forwards.
  return `${window.location.origin}${path}`
}

/** A webcal: link, which Apple Calendar and most desktop clients open directly. */
export function webcalUrl(httpUrl: string): string {
  return httpUrl.replace(/^https?:/, 'webcal:')
}

// ---------------------------------------------------------------------------
// Wanted list and retailers (Batch 18) — §5.1, §5.2
// ---------------------------------------------------------------------------

export async function fetchWanted(activeOnly = false): Promise<WantedList> {
  return parseResponse(
    await authFetch(`/wanted?activeOnly=${String(activeOnly)}`),
    wantedListSchema,
  )
}

export interface WantedInput {
  /** Exactly one of these. A wanted film usually has no `movies` row — that is the whole
   *  point of wanting it — so `tmdbId` is the common case, not the exception. */
  movieId?: string
  tmdbId?: number
  preferredFormat?: string | null
  maxPrice?: string | null
  currency?: string
  notes?: string | null
}

export async function addWanted(input: WantedInput): Promise<WantedItem> {
  return parseOrThrowApiError(
    await authFetch('/wanted', {
      method: 'POST',
      body: JSON.stringify({ currency: 'GBP', ...input }),
    }),
    wantedItemSchema,
  )
}

export async function updateWanted(
  id: string,
  input: { preferredFormat?: string | null; maxPrice?: string | null; isActive: boolean; notes?: string | null },
): Promise<WantedItem> {
  return parseOrThrowApiError(
    await authFetch(`/wanted/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ currency: 'GBP', ...input }),
    }),
    wantedItemSchema,
  )
}

export async function removeWanted(id: string): Promise<void> {
  const response = await authFetch(`/wanted/${id}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await errorMessage(response))
}

/**
 * §11.2's "bulk add missing to wanted list", which Batch 13 dropped for want of a table.
 *
 * Sequential rather than parallel, and it does not stop at the first failure: a film
 * already on the list answers 409, and one bad entry in a set of forty should not abandon
 * the other thirty-nine. The result says what actually happened.
 */
export async function addManyWanted(
  tmdbIds: number[],
  preferredFormat?: string | null,
): Promise<{ added: number; alreadyThere: number; failed: number }> {
  let added = 0
  let alreadyThere = 0
  let failed = 0
  for (const tmdbId of tmdbIds) {
    try {
      await addWanted({ tmdbId, preferredFormat })
      added += 1
    } catch (error) {
      // 409 is "already on the list", which is a success from the person's point of view.
      if (error instanceof ApiError && error.status === 409) alreadyThere += 1
      else failed += 1
    }
  }
  return { added, alreadyThere, failed }
}

export async function fetchRetailers(): Promise<RetailerList> {
  return parseResponse(await authFetch('/retailers'), retailerListSchema)
}

export interface RetailerInput {
  name: string
  baseUrl: string
  dealsUrl?: string | null
  searchUrlTemplate?: string | null
  scraperType?: ScraperType
  scraperConfig?: Record<string, unknown>
  scrapeFrequency?: ScrapeFrequency
  enabled?: boolean
  currency?: string
  region?: string
  notes?: string | null
}

function retailerBody(input: RetailerInput) {
  return {
    scraperType: 'generic_css',
    scraperConfig: {},
    scrapeFrequency: 'weekly',
    enabled: true,
    currency: 'GBP',
    region: 'GB',
    ...input,
  }
}

export async function addRetailer(input: RetailerInput): Promise<RetailerRow> {
  return parseOrThrowApiError(
    await authFetch('/retailers', { method: 'POST', body: JSON.stringify(retailerBody(input)) }),
    retailerSchema,
  )
}

export async function updateRetailer(id: string, input: RetailerInput): Promise<RetailerRow> {
  return parseOrThrowApiError(
    await authFetch(`/retailers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(retailerBody(input)),
    }),
    retailerSchema,
  )
}

export async function removeRetailer(id: string): Promise<void> {
  const response = await authFetch(`/retailers/${id}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await errorMessage(response))
}

export async function seedRetailers(): Promise<RetailerSeed> {
  return parseOrThrowApiError(
    await authFetch('/retailers/seed', { method: 'POST' }),
    retailerSeedSchema,
  )
}

// ---------------------------------------------------------------------------
// Scraper framework (Batch 19) — §5.3, §5.4
// ---------------------------------------------------------------------------

export async function fetchBuiltInScrapers(): Promise<BuiltInScraperList> {
  return parseResponse(await authFetch('/scrapers/built-in'), builtInScraperListSchema)
}

export async function applyBuiltInScrapers(): Promise<BuiltInScraperList> {
  return parseOrThrowApiError(
    await authFetch('/scrapers/apply-built-ins', { method: 'POST' }),
    builtInScraperListSchema,
  )
}

/**
 * §5.4's "test scraper". **This makes the server fetch the URL**, so it is slow and it is
 * a real request to a real shop — which is why it is a button a person presses rather than
 * anything automatic.
 */
export async function testScraper(input: {
  url: string
  scraperConfig: Record<string, unknown>
  expectedTitle?: string | null
  expectedCurrency?: string
}): Promise<ScraperTest> {
  return parseOrThrowApiError(
    await authFetch('/scrapers/test', {
      method: 'POST',
      body: JSON.stringify({ expectedCurrency: 'GBP', ...input }),
    }),
    scraperTestSchema,
  )
}

/** Dry by default, matching the endpoint — this hits real shops. */
export async function runScrapers(dryRun = true): Promise<ScrapeRun> {
  return parseOrThrowApiError(
    await authFetch(`/scrapers/run?dryRun=${String(dryRun)}`, { method: 'POST' }),
    scrapeRunSchema,
  )
}
