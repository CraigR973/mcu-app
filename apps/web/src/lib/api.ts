import {
  activitySchema,
  aiAnswerSchema,
  aiConversationDetailSchema,
  aiConversationListSchema,
  aiConversationSchema,
  aiToolListSchema,
  aiSettingsSchema,
  aiStatusSchema,
  aiUsageSchema,
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
  collectionMoveResponseSchema,
  bidTrialSchema,
  bidTrialStartSchema,
  collectionValueSchema,
  completionInsightsSchema,
  completionRefreshSchema,
  completionSetDetailSchema,
  duplicateCheckSchema,
  barcodeLookupSchema,
  attentionSchema,
  dealListSchema,
  dealSchema,
  dealsRunSchema,
  ebayListingUrlSchema,
  ebayPriceEstimateSchema,
  itemPhotoListSchema,
  itemPhotoSchema,
  movieDetailSchema,
  moviePageSchema,
  movieNightCandidateListSchema,
  movieNightSessionListSchema,
  movieNightSessionSchema,
  movieNightVoteResultSchema,
  notificationListSchema,
  notificationPreferenceSchema,
  onThisDayMemoriesSchema,
  newReleaseListSchema,
  builtInScraperListSchema,
  retailerListSchema,
  retailerSchema,
  retailerSeedSchema,
  scraperTestSchema,
  scrapeRunSchema,
  scrapeRunListSchema,
  aggregationSchema,
  dailyRunSchema,
  recommendationListSchema,
  rewatchSuggestionsSchema,
  highlightsSchema,
  streamingSchema,
  profileResponseSchema,
  pushDeviceStatusSchema,
  pushSubscriptionListSchema,
  pushSubscriptionSchema,
  reminderRunSchema,
  testNotificationSchema,
  vapidKeySchema,
  loanListSchema,
  loanSchema,
  purgePreviewSchema,
  searchResponseSchema,
  beyondSearchResponseSchema,
  externalFilmSchema,
  type BeyondSearchResponse,
  type ExternalFilm,
  smartCollectionListSchema,
  navSectionsSchema,
  syncResponseSchema,
  watchHistoryStatusSchema,
  statsSchema,
  valuationStartSchema,
  specBackfillSchema,
  specBatchStartSchema,
  specDecisionSchema,
  specQueueSchema,
  ebayAccountSchema,
  ebayConnectStartSchema,
  ebaySellingSchema,
  ebayTargetSchema,
  ebayTargetsSchema,
  ebayWatchingSchema,
  identifyDecisionSchema,
  identifyOverviewSchema,
  identifyQueueSchema,
  identifySearchSchema,
  recentIdentificationsSchema,
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
  type Attention,
  type BarcodeCandidate,
  type BarcodeLookup,
  type Deal,
  type DealList,
  type DealsRun,
  type EbayListingUrl,
  type EbayPriceEstimate,
  type BidTrial,
  type BidTrialStart,
  type CollectionValue,
  type ValuationStart,
  type SpecBackfill,
  type SpecBatchStart,
  type SpecDecision,
  type SpecQueue,
  type EbayTarget,
  type EbayTargets,
  type IdentifyDecision,
  type IdentifyOverview,
  type IdentifyQueue,
  type IdentifySearch,
  type RecentIdentifications,
  type AiAnswer,
  type AiConversation,
  type AiConversationDetail,
  type AiConversationList,
  type AiToolList,
  type AiSettings,
  type AiStatus,
  type AiUsage,
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
  type CollectionMoveResponse,
  type CompletionInsights,
  type CompletionRefresh,
  type CompletionSetDetail,
  type CompletionSetType,
  type Condition,
  type DuplicateCheck,
  type DuplicateReason,
  type ItemPhoto,
  type ItemPhotoList,
  type Loan,
  type LoanList,
  type PurgePreview,
  type MovieDetail,
  type MoviePage,
  type MovieNightCandidateList,
  type MovieNightSession,
  type MovieNightSessionList,
  type MovieNightVoteResult,
  type NotificationList,
  type NotificationPreference,
  type NotificationRecord,
  type OnThisDayMemory,
  type NewReleaseList,
  type OfferKind,
  type RecommendationList,
  type RewatchSuggestion,
  type Highlights,
  type RetailerList,
  type RetailerRow,
  type BuiltInScraperList,
  type RetailerSeed,
  type ScrapeFrequency,
  type Aggregation,
  type DailyRun,
  type ScrapeRun,
  type ScrapeRunList,
  type ScrapeRunRecord,
  type ScraperTest,
  type ScraperType,
  type Streaming,
  type ProfileResponse,
  type PushDeviceStatus,
  type PushSubscriptionList,
  type PushSubscriptionRecord,
  type ReminderRun,
  type SearchResponse,
  type TestNotificationResult,
  type VapidKey,
  type SmartCollection,
  type SmartCollectionFilters,
  type SmartCollectionList,
  type SmartCollectionResults,
  type NavSections,
  type SyncResponse,
  type WatchHistoryStatus,
  type Stats,
  type TmdbSearchResponse,
  type TrashList,
  type TrashPage,
  type WantedItem,
  type WantedList,
  type TrashTable,
  type WatchLogEntry,
  type WatchLogPage,
  type EbayAccount,
  type EbaySelling,
  type EbayWatching,
  type ShelfFacet,
  type MovieListItem,
} from '@mcu/shared'
import { z, type ZodType, type ZodTypeDef } from 'zod'

import { authFetch } from './auth-tokens'
import { formatShortDate } from './utils'

export type {
  Activity,
  Attention,
  ActivityEvent,
  ActivityKind,
  BarcodeCandidate,
  BarcodeLookup,
  Deal,
  DealList,
  DealsRun,
  EbayListingUrl,
  EbayPriceEstimate,
  EbayPriceSegment,
  EbayUsedValue,
  ValueBasis,
  BidTrial,
  BidTrialStart,
  CollectionValue,
  TrialFilm,
  TrialSummary,
  CopyValuation,
  ValuationRun,
  ValuationStart,
  SpecBackfill,
  SpecBatchStart,
  SpecCandidate,
  SpecCoverage,
  SpecDecision,
  SpecQueue,
  SpecQueueItem,
  SpecRun,
  EbayTarget,
  EbayTargets,
  EbayWatchRun,
  FilmInCollection,
  IdentifyCandidate,
  IdentifyDecision,
  IdentifyOverview,
  IdentifyQueue,
  IdentifyQueueItem,
  IdentifyRun,
  IdentifySearch,
  RecentIdentification,
  RecentIdentifications,
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
  Highlights,
  RewatchedFilm,
  TopRatedFilm,
  ValuableDisc,
  CollectionItem,
  CollectionMoveResponse,
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
  NavSections,
  SyncRun,
  SyncResponse,
  WatchHistoryStatus,
  OnThisDayMemory,
  NewRelease,
  NewReleaseList,
  OfferKind,
  OwnershipState,
  Recommendation,
  RecommendationList,
  RewatchSuggestion,
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
  BeyondResult,
  BeyondSearchResponse,
  ExternalFilm,
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
  EbayAccount,
  EbayListing,
  EbaySavedSearch,
  EbaySelling,
  EbaySold,
  EbayWatching,
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
  /** Set when a server answered with a 5xx or 408: it answered, so this is not "no signal". */
  readonly status?: number

  constructor(
    message: string,
    readonly mayHaveLanded: boolean,
    options?: { cause?: unknown; status?: number },
  ) {
    super(message, options)
    this.name = 'NetworkError'
    this.status = options?.status
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
    throw new NetworkError('The server did not answer.', true, { status: response.status })
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

/**
 * `unknown` as the schema's *input* type, because that is what arrives: the body is
 * parsed, not trusted. Typing it `ZodType<T>` quietly required input and output to match,
 * which ruled out `.default()` — and Batch T2 needs one, so a response the service worker
 * cached before a field existed still parses offline.
 */
type ResponseSchema<T> = ZodType<T, ZodTypeDef, unknown>

async function parseResponse<T>(response: Response, schema: ResponseSchema<T>): Promise<T> {
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
  const body: unknown = await response.json()
  return schema.parse(body)
}

/** As `parseResponse`, but a refused request raises a typed {@link ApiError}. */
async function parseOrThrowApiError<T>(
  response: Response,
  schema: ResponseSchema<T>,
): Promise<T> {
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
  /** Batch T3, snag 2 — minutes, inclusive. A film with no known runtime is left out
   *  whenever either is set, as it is for the rating. */
  runtimeMin?: number
  runtimeMax?: number
  watched?: boolean
  /** Mark's request, 14 Oct: films TMDB has not matched and nobody has set aside as TV or
   *  not a film, so he can identify each from its page. The Archive only; not saved. */
  toIdentify?: boolean
  /** §3.9's spec filters. They read what Batch 23 fetched from Blu-ray.com, so a
   *  collection whose specs have never been fetched answers all of them with nothing —
   *  which is correct rather than broken. */
  hdr?: string
  audio?: string
  label?: string
  regionFree?: boolean
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
  if (filters.runtimeMin != null) params.set('runtimeMin', String(filters.runtimeMin))
  if (filters.runtimeMax != null) params.set('runtimeMax', String(filters.runtimeMax))
  if (filters.watched != null) params.set('watched', String(filters.watched))
  if (filters.toIdentify != null) params.set('toIdentify', String(filters.toIdentify))
  // §3.9 asks for these to be URL-encoded so a filtered view is bookmarkable, which
  // is what they already are — the page's own URL carries them.
  if (filters.hdr) params.set('hdr', filters.hdr)
  if (filters.audio) params.set('audio', filters.audio)
  if (filters.label) params.set('label', filters.label)
  if (filters.regionFree) params.set('regionFree', 'true')
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
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
}

/** Batch 37: private watches from this calendar day in prior years. */
export async function fetchOnThisDayMemories(): Promise<OnThisDayMemory[]> {
  return parseResponse(await authFetch('/memories/on-this-day'), onThisDayMemoriesSchema)
}

/** Batch 37: personally highly rated films not watched recently. */
/** Home's Highlights, three rows in one request — Batch V5. */
export async function fetchHighlights(): Promise<Highlights> {
  return parseResponse(await authFetch('/highlights'), highlightsSchema)
}

export async function fetchRewatchSuggestions(): Promise<RewatchSuggestion[]> {
  return parseResponse(
    await authFetch('/memories/rewatch-suggestions'),
    rewatchSuggestionsSchema,
  )
}

/** §3.7's half-star scale, for a star control that must not invent its own steps. */
export const RATING_STEPS = [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5] as const

/** The TMDB-rating thresholds the filter bar offers. */
export const MIN_RATING_OPTIONS = [9, 8, 7, 6, 5] as const

export async function fetchMovie(id: string): Promise<MovieDetail> {
  return parseResponse(await authFetch(`/movies/${id}`), movieDetailSchema)
}

export async function fetchCopies(
  movieId: string,
  /** Include discs that have been sold or donated. Off by default, because everywhere
   *  else "copies" means the ones you still own — §4.4. The film's page turns it on so
   *  "removes from active views" does not come to mean "unreachable". */
  includeSold = false,
): Promise<CollectionCopy[]> {
  const path = includeSold ? `/movies/${movieId}/copies?includeSold=true` : `/movies/${movieId}/copies`
  return parseResponse(await authFetch(path), collectionCopiesSchema)
}

export async function fetchSearch(q: string, limit = 20): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) })
  return parseResponse(await authFetch(`/search?${params}`), searchResponseSchema)
}

/** Batch T2 — films matching a search that are *not* on the shelf, from TMDB. */
export async function fetchSearchBeyond(q: string): Promise<BeyondSearchResponse> {
  const params = new URLSearchParams({ q })
  return parseResponse(await authFetch(`/search/beyond?${params}`), beyondSearchResponseSchema)
}

/** Batch T2 — the card for a film the collection does not hold. */
export async function fetchExternalFilm(tmdbId: number): Promise<ExternalFilm> {
  return parseResponse(await authFetch(`/films/tmdb/${tmdbId}`), externalFilmSchema)
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

/** Identify a title as a TMDB film or, with `mediaType: 'tv'`, a TMDB series (Batch Y3). */
export async function identifyMovie(
  movieId: string,
  tmdbId: number,
  mediaType: 'film' | 'tv' = 'film',
): Promise<MovieDetail> {
  return parseResponse(
    await authFetch(`/movies/${movieId}/identify`, {
      method: 'POST',
      body: JSON.stringify({ tmdbId, mediaType }),
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

export function formatLabel(value: string | null): string | null {
  if (!value) return null
  return FORMATS.find((format) => format.value === value)?.label ?? value.replaceAll('_', ' ')
}

/** How a picker names a shelf, or one of the Lounge's sides (14 Oct): "2nd shelf",
 *  "Left hand side". The API says; an older cached answer without the label gets the old
 *  wording. */
export function shelfLabel(entry: ShelfFacet): string {
  return entry.label ?? `${entry.shelf} shelf`
}

/** Whether a title is one the Archive's "Still to identify" lists: TMDB has matched it to
 *  neither a film nor a series, and it is not set aside as not a film (Mark, 15 Oct; a series
 *  set aside is identified as one since Batch Y3). The badge read `identified` alone, so a
 *  set-aside title was flagged but never listed. */
export function needsIdentifying(movie: Pick<MovieListItem, 'identified' | 'setAsideAs'>): boolean {
  return !movie.identified && movie.setAsideAs !== 'not_film'
}

/** A title identified as a TMDB series (Batch Y3), which a card labels "TV series". */
export function isIdentifiedSeries(movie: Pick<MovieListItem, 'identified' | 'mediaType'>): boolean {
  return movie.identified && movie.mediaType === 'tv'
}

/**
 * Which format a copy **is**, when its `formats` array names several.
 *
 * `FORMATS` is in best-to-worst order, mirroring the API's `FORMAT_RANK` and the
 * `recalculate_movie_derived_fields` trigger that enforces it. A combo pack holding a 4K
 * disc and a Blu-ray is a 4K item: that is what is in the box, and it is what a price for
 * it has to be a price *of*.
 */
export function bestFormat(formats: readonly string[]): string | null {
  return FORMATS.find((format) => formats.includes(format.value))?.value ?? formats[0] ?? null
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
  /** Batch U2. Left out, the API keeps what is there, so an older build cannot clear it. */
  edition?: string | null
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
  barcode?: string
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

/** One disc and where it goes — Batch Y2. `location` only when restoring free text. */
export interface CollectionMoveEntry {
  itemId: string
  baseUpdatedAt: string
  location?: string | null
  section: string | null
  shelf: string | null
}

/** Move many discs at once, or put them back — Batch Y2 (`DECISIONS.md` #265). */
export async function moveCollectionItems(moves: CollectionMoveEntry[]): Promise<CollectionMoveResponse> {
  return parseOrThrowApiError(
    await send('/collection/move', { method: 'POST', body: JSON.stringify({ moves }) }),
    collectionMoveResponseSchema,
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
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
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
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
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
  if (filters.runtimeMin !== null) out.runtimeMin = filters.runtimeMin
  if (filters.runtimeMax !== null) out.runtimeMax = filters.runtimeMax
  if (filters.watched !== null) out.watched = filters.watched
  return out
}

/** Batch T3. How a runtime range is said: "90–120 min", "at least 90 min", "up to 2 hours". */
export function runtimeLabel(min: number | null | undefined, max: number | null | undefined): string | null {
  if (min != null && max != null) return `${String(min)}–${String(max)} min`
  if (min != null) return `at least ${String(min)} min`
  if (max != null) return `up to ${String(max)} min`
  return null
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
  const runtime = runtimeLabel(filters.runtimeMin, filters.runtimeMax)
  if (runtime) parts.push(runtime)
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
// Watch history sync (Batch S5) — snag 10a
// ---------------------------------------------------------------------------

export async function fetchWatchHistoryStatus(): Promise<WatchHistoryStatus> {
  return parseResponse(await authFetch('/watch-history/status'), watchHistoryStatusSchema)
}

export async function setLetterboxdUsername(
  letterboxdUsername: string | null,
): Promise<WatchHistoryStatus> {
  return parseOrThrowApiError(
    await authFetch('/watch-history/username', {
      method: 'PUT',
      body: JSON.stringify({ letterboxdUsername }),
    }),
    watchHistoryStatusSchema,
  )
}

/** Fetch the diary feed and write whatever is new.
 *
 *  **The only live third-party request the app makes on a button press.** It is a button
 *  rather than a schedule because both Railway crons have been crashing on every fire
 *  since 2026-09-10 (`DECISIONS.md` #156), and a design that assumed a schedule would
 *  have shipped inert. */
export async function syncWatchHistory(): Promise<SyncResponse> {
  return parseOrThrowApiError(
    await authFetch('/watch-history/sync', { method: 'POST' }),
    syncResponseSchema,
  )
}

// ---------------------------------------------------------------------------
// Navigation shape (Batch S3) — snag 5, `DECISIONS.md` #154
// ---------------------------------------------------------------------------

/** Which self-hiding destinations have anything behind them.
 *
 *  Read by the shell on every page, so it is deliberately the cheapest call in the app:
 *  four `COUNT(*)`s in one round trip, where the alternative was fetching four full lists
 *  to discover they were empty. */
export async function fetchNavSections(): Promise<NavSections> {
  return parseResponse(await authFetch('/nav/sections'), navSectionsSchema)
}

// ---------------------------------------------------------------------------
// Stats, activity and export (Batch 14) — §13.1–13.4
// ---------------------------------------------------------------------------

/**
 * Batch T6 — the owned discs at their stored eBay asking prices, and how many have one.
 * Reading spends nothing: the prices were stored by a valuation run.
 */
export async function fetchCollectionValue(): Promise<CollectionValue> {
  return parseResponse(await authFetch('/collection/value'), collectionValueSchema)
}

/**
 * Admin-only. Starts pricing whatever is due, within today's share of eBay's allowance.
 * `outcome` says whether anything started; only `started` spends eBay calls.
 */
export async function startValuationRun(): Promise<ValuationStart> {
  return parseOrThrowApiError(
    await authFetch('/collection/value/refresh', { method: 'POST' }),
    valuationStartSchema,
  )
}

/**
 * Batch V6 — the latest bid trial and its report, or null before the first. Admin only.
 * Reading spends nothing.
 */
export async function fetchBidTrial(): Promise<BidTrial | null> {
  return parseResponse(await authFetch('/collection/value/bid-trial'), bidTrialSchema.nullable())
}

/**
 * Admin-only. Starts a bid trial within today's share of eBay's allowance: one search each for
 * up to 100 priced films, Buy It Now and auctions together. It saves no prices.
 */
export async function startBidTrial(): Promise<BidTrialStart> {
  return parseOrThrowApiError(
    await authFetch('/collection/value/bid-trial', { method: 'POST' }),
    bidTrialStartSchema,
  )
}

/** Batch T7 — how far the Blu-ray.com backfill has got, and its Brave spend. Admin only. */
export async function fetchSpecBackfill(): Promise<SpecBackfill> {
  return parseResponse(await authFetch('/specs/backfill'), specBackfillSchema)
}

/** Discs waiting for Craig to pick a Blu-ray.com page, paste one, or skip. */
export async function fetchSpecQueue(limit = 20): Promise<SpecQueue> {
  return parseResponse(await authFetch(`/specs/queue?limit=${String(limit)}`), specQueueSchema)
}

/** Craig's choice of page. Nothing is fetched now: the next batch does it. */
export async function acceptSpecPage(lookupId: string, url: string): Promise<SpecDecision> {
  return parseOrThrowApiError(
    await authFetch(`/specs/queue/${lookupId}/accept`, { method: 'POST', body: JSON.stringify({ url }) }),
    specDecisionSchema,
  )
}

export async function skipSpecDisc(lookupId: string): Promise<SpecDecision> {
  return parseOrThrowApiError(
    await authFetch(`/specs/queue/${lookupId}/skip`, { method: 'POST' }),
    specDecisionSchema,
  )
}

/** One batch now rather than tonight, within the same budgets. Only `started` does anything. */
export async function startSpecBatch(): Promise<SpecBatchStart> {
  return parseOrThrowApiError(await authFetch('/specs/backfill/run', { method: 'POST' }), specBatchStartSchema)
}

/** Batch T9 — how many unmatched films wait, and what became of the rest. Admin only. */
export async function fetchIdentifyOverview(): Promise<IdentifyOverview> {
  return parseResponse(await authFetch('/identify/overview'), identifyOverviewSchema)
}

/** Films waiting for Craig, with the films offered and why each waits. */
export async function fetchIdentifyQueue(limit = 20): Promise<IdentifyQueue> {
  return parseResponse(await authFetch(`/identify/queue?limit=${String(limit)}`), identifyQueueSchema)
}

/** TMDB's films for a corrected title. Nothing is saved until one is picked. */
export async function searchIdentify(movieId: string, query: string): Promise<IdentifySearch> {
  return parseOrThrowApiError(
    await authFetch(`/identify/films/${movieId}/search?query=${encodeURIComponent(query)}`),
    identifySearchSchema,
  )
}

/** Craig's choice. `merge` says he has seen both films and means to join them. */
export async function identifyFilm(
  movieId: string,
  tmdbId: number,
  options: { merge?: boolean; searched?: boolean } = {},
): Promise<IdentifyDecision> {
  return parseOrThrowApiError(
    await authFetch(`/identify/films/${movieId}/identify`, {
      method: 'POST',
      body: JSON.stringify({ tmdbId, merge: options.merge ?? false, searched: options.searched ?? false }),
    }),
    identifyDecisionSchema,
  )
}

export async function setFilmAside(movieId: string, kind: 'tv' | 'not_film'): Promise<IdentifyDecision> {
  return parseOrThrowApiError(
    await authFetch(`/identify/films/${movieId}/set-aside`, { method: 'POST', body: JSON.stringify({ kind }) }),
    identifyDecisionSchema,
  )
}

export async function skipFilm(movieId: string): Promise<IdentifyDecision> {
  return parseOrThrowApiError(await authFetch(`/identify/films/${movieId}/skip`, { method: 'POST' }), identifyDecisionSchema)
}

export async function fetchRecentIdentifications(limit = 20): Promise<RecentIdentifications> {
  return parseResponse(await authFetch(`/identify/recent?limit=${String(limit)}`), recentIdentificationsSchema)
}

/** Put a film back as it was before that identification, merges included. */
export async function undoIdentification(actionId: string): Promise<IdentifyDecision> {
  return parseOrThrowApiError(await authFetch(`/identify/recent/${actionId}/undo`, { method: 'POST' }), identifyDecisionSchema)
}

// ---------------------------------------------------------------------------
// eBay price alerts (Batch T8a)
// ---------------------------------------------------------------------------

/** The react-query key every price-alert list shares, so one change refreshes them all. */
export const EBAY_TARGETS_KEY = ['ebay-targets'] as const

/** The signed-in person's price alerts, and when the schedule last checked them. */
export async function fetchEbayTargets(movieId?: string): Promise<EbayTargets> {
  const query = movieId ? `?movieId=${encodeURIComponent(movieId)}` : ''
  return parseResponse(await authFetch(`/ebay/targets${query}`), ebayTargetsSchema)
}

/** An alert on one listing, from the address copied from eBay. Reads the listing once. */
export async function createListingTarget(address: string, targetPrice: string): Promise<EbayTarget> {
  return parseOrThrowApiError(
    await authFetch('/ebay/targets/listing', {
      method: 'POST',
      body: JSON.stringify({ address, targetPrice }),
    }),
    ebayTargetSchema,
  )
}

/** An alert on any UK Buy It Now copy of a film on a format. */
export async function createSearchTarget(
  movieId: string,
  formatCode: 'blu_ray' | '4k_uhd' | 'dvd',
  targetPrice: string,
): Promise<EbayTarget> {
  return parseOrThrowApiError(
    await authFetch('/ebay/targets/search', {
      method: 'POST',
      body: JSON.stringify({ movieId, formatCode, targetPrice }),
    }),
    ebayTargetSchema,
  )
}

export async function changeTargetPrice(id: string, targetPrice: string): Promise<EbayTarget> {
  return parseOrThrowApiError(
    await authFetch(`/ebay/targets/${id}`, { method: 'PATCH', body: JSON.stringify({ targetPrice }) }),
    ebayTargetSchema,
  )
}

export async function removeTarget(id: string): Promise<void> {
  const response = await authFetch(`/ebay/targets/${id}`, { method: 'DELETE' })
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
}

// ---------------------------------------------------------------------------
// Connect eBay (Batch T8b) — each person's own eBay, `DECISIONS.md` #245
// ---------------------------------------------------------------------------

/** This person's connection, with the account's name read live from eBay. */
export async function fetchEbayAccount(): Promise<EbayAccount> {
  return parseResponse(await authFetch('/ebay/account'), ebayAccountSchema)
}

/** Start connecting: the API keeps a one-time state and answers eBay's consent address. */
export async function startEbayConnect(): Promise<string> {
  const started = await parseOrThrowApiError(
    await authFetch('/ebay/account/connect', { method: 'POST' }),
    ebayConnectStartSchema,
  )
  return started.authorizeUrl
}

/** Finish connecting with what eBay put on the address it sent the person back to. */
export async function finishEbayConnect(code: string, state: string): Promise<EbayAccount> {
  return parseOrThrowApiError(
    await authFetch('/ebay/account/complete', {
      method: 'POST',
      body: JSON.stringify({ code, state }),
    }),
    ebayAccountSchema,
  )
}

export async function disconnectEbay(): Promise<void> {
  const response = await authFetch('/ebay/account', { method: 'DELETE' })
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
}

export async function fetchEbayWatching(): Promise<EbayWatching> {
  return parseOrThrowApiError(await authFetch('/ebay/account/watching'), ebayWatchingSchema)
}

export async function fetchEbaySelling(): Promise<EbaySelling> {
  return parseOrThrowApiError(await authFetch('/ebay/account/selling'), ebaySellingSchema)
}

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
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)

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
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
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
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
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
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
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

/**
 * A loan names its borrower one way — Batch W3 (#249): a name for anyone, or the profile of
 * one of the people who use the app ("I'm borrowing it"), whose name the API fills in.
 */
export type LendInput = {
  collectionItemId: string
  lentDate?: string
  dueDate?: string | null
  notes?: string | null
} & ({ borrowerName: string; borrowerProfileId?: never } | { borrowerProfileId: string; borrowerName?: never })

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
  if (loan.returnedDate) return `returned ${formatShortDate(loan.returnedDate)}`
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
  /** Which edition within that format — free text, e.g. "Arte Originale Slipcover". */
  preferredEdition?: string | null
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
  input: {
    preferredFormat?: string | null
    preferredEdition?: string | null
    maxPrice?: string | null
    // Carried explicitly for the reason the whole body is: `PUT /wanted/{id}` replaces the
    // row, so a currency left out here is a currency reset to GBP.
    currency?: string
    isActive: boolean
    notes?: string | null
  },
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
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
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
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
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
  /** The retailer's search **template**, sent verbatim — `{query}` and `{format}` are
   *  substituted by the server, using the same function a real run uses. Replacing them
   *  here is what sent Zavvi the literal string `{format}` (`DECISIONS.md` #99). */
  url: string
  scraperConfig: Record<string, unknown>
  expectedTitle?: string | null
  expectedCurrency?: string
  preferredFormat?: string | null
  expectedHost?: string | null
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

// ---------------------------------------------------------------------------
// Notifications and push (Batch 11) — §6.1, §6.2, §5.11
// ---------------------------------------------------------------------------

export async function fetchVapidKey(): Promise<VapidKey> {
  return parseResponse(await authFetch('/notifications/vapid-key'), vapidKeySchema)
}

export async function fetchPushSubscriptions(): Promise<PushSubscriptionList> {
  return parseResponse(await authFetch('/notifications/subscriptions'), pushSubscriptionListSchema)
}

/** Batch X3: what the server holds for this browser's subscription, by its endpoint. */
export async function fetchPushDeviceStatus(endpoint: string): Promise<PushDeviceStatus> {
  return parseResponse(
    await authFetch('/notifications/subscriptions/status', {
      method: 'POST',
      body: JSON.stringify({ endpoint }),
    }),
    pushDeviceStatusSchema,
  )
}

/**
 * Register this browser.
 *
 * The body is the browser's own `subscription.toJSON()` plus a label, passed through
 * without transcription — `p256dh` retyped by hand is a subscription that encrypts to
 * nobody, and the push service still answers `201`.
 */
export async function registerPushSubscription(
  subscription: PushSubscriptionJSON,
  deviceLabel: string,
): Promise<PushSubscriptionRecord> {
  const query = new URLSearchParams({ userAgent: navigator.userAgent.slice(0, 300) })
  return parseOrThrowApiError(
    await authFetch(`/notifications/subscriptions?${query.toString()}`, {
      method: 'POST',
      body: JSON.stringify({ ...subscription, deviceLabel }),
    }),
    pushSubscriptionSchema,
  )
}

export async function removePushSubscription(id: string): Promise<void> {
  const response = await authFetch(`/notifications/subscriptions/${id}`, { method: 'DELETE' })
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
}

export async function sendTestNotification(id: string): Promise<TestNotificationResult> {
  return parseOrThrowApiError(
    await authFetch(`/notifications/subscriptions/${id}/test`, { method: 'POST' }),
    testNotificationSchema,
  )
}

export async function fetchNotificationPreferences(): Promise<NotificationPreference> {
  return parseResponse(await authFetch('/notifications/preferences'), notificationPreferenceSchema)
}

export interface NotificationPreferenceInput {
  dealsEnabled?: boolean
  saleEventsEnabled?: boolean
  releasesEnabled?: boolean
  loansEnabled?: boolean
  movieNightEnabled?: boolean
  digestMode?: boolean
  digestHourLocal?: number
  quietHoursStart?: string
  quietHoursEnd?: string
  clearQuietHours?: boolean
  quietHoursTimezone?: string
}

export async function updateNotificationPreferences(
  input: NotificationPreferenceInput,
): Promise<NotificationPreference> {
  return parseOrThrowApiError(
    await authFetch('/notifications/preferences', {
      method: 'PUT',
      body: JSON.stringify(input),
    }),
    notificationPreferenceSchema,
  )
}

export async function fetchNotifications(limit = 50): Promise<NotificationList> {
  return parseResponse(await authFetch(`/notifications?limit=${limit}`), notificationListSchema)
}

/** Run the reminder senders. `asOf` is what makes §5.11's acceptance testable. */
export async function runReminders(asOf?: string): Promise<ReminderRun> {
  const query = asOf ? `?asOf=${encodeURIComponent(asOf)}` : ''
  return parseOrThrowApiError(
    await authFetch(`/notifications/run-reminders${query}`, { method: 'POST' }),
    reminderRunSchema,
  )
}

export async function seedSaleSeasons(year?: number): Promise<ReminderRun> {
  const query = year ? `?year=${year}` : ''
  return parseOrThrowApiError(
    await authFetch(`/notifications/seed-sale-seasons${query}`, { method: 'POST' }),
    reminderRunSchema,
  )
}

/** How a notification's state reads to a person — the "why did I not get that" answer. */
export function notificationStateLabel(notification: NotificationRecord): string {
  if (notification.status === 'sent') {
    const devices = notification.deliveredCount
    return `Sent to ${devices} device${devices === 1 ? '' : 's'}`
  }
  if (notification.status === 'suppressed') {
    return notification.suppressedReason === 'category_disabled'
      ? 'Not sent — that category is switched off'
      : 'Not sent — no devices are registered'
  }
  if (notification.status === 'failed') return 'Could not be delivered'
  if (notification.deferredReason === 'quiet_hours') return 'Waiting — quiet hours'
  if (notification.deferredReason === 'digest') return 'Waiting for your daily digest'
  return 'Waiting to be sent'
}

// ---------------------------------------------------------------------------
// Daily scraping, drop alerts and the roll-up (Batch 20) — §5.5, §5.6, §5.8
// ---------------------------------------------------------------------------

export async function fetchScrapeRuns(limit = 20): Promise<ScrapeRunList> {
  return parseResponse(await authFetch(`/scrapers/runs?limit=${limit}`), scrapeRunListSchema)
}

/**
 * The nightly pass, run now.
 *
 * `dryRun` defaults to **false**, unlike `/scrapers/run` — this is the scheduled job, and
 * a version of it that quietly wrote nothing would be indistinguishable from one that
 * worked. Pass `true` deliberately to rehearse it.
 */
export async function runDailyScrape(dryRun = false): Promise<DailyRun> {
  const query = new URLSearchParams({ dryRun: String(dryRun), trigger: 'manual' })
  return parseOrThrowApiError(
    await authFetch(`/scrapers/daily?${query.toString()}`, { method: 'POST' }),
    dailyRunSchema,
  )
}

export async function aggregatePriceHistory(olderThanDays = 90): Promise<Aggregation> {
  return parseOrThrowApiError(
    await authFetch(`/scrapers/aggregate?olderThanDays=${olderThanDays}`, { method: 'POST' }),
    aggregationSchema,
  )
}

/**
 * How a run reads against §5.5's corrected criterion.
 *
 * `written` is compared with the pairs that were genuinely answerable — attempted minus
 * not-stocked — because no shop stocks every film (`DECISIONS.md` #112). A run where
 * nothing was answerable is "nothing to do", not a failure.
 */
export function scrapeRunVerdict(run: ScrapeRunRecord): {
  answerable: number
  ok: boolean
  label: string
} {
  // **`attempted` already excludes `notStocked`** (`DECISIONS.md` #107), so subtracting it
  // here counted it twice: a real run of 17 attempted against 23 not-stocked read as
  // "Nothing to price" over six priced discs. The only pairs left to remove are the ones
  // whose shop answered with nothing at all. #125.
  const answerable = Math.max(run.attempted - (run.noResults ?? 0), 0)
  if (run.error) return { answerable, ok: false, label: 'Run failed' }
  if (answerable === 0) {
    return { answerable, ok: true, label: 'Nothing to price — no shop had any of the wants' }
  }
  const ok = run.written >= answerable * 0.9
  return {
    answerable,
    ok,
    label: ok
      ? `${run.written} of ${answerable} priced`
      : `Only ${run.written} of ${answerable} priced — check the failures`,
  }
}

// ---------------------------------------------------------------------------
// AI assistant — client and caps (Batch 30) — §9.1, §9.7
// ---------------------------------------------------------------------------

export async function fetchAiStatus(): Promise<AiStatus> {
  return parseResponse(await authFetch('/ai/status'), aiStatusSchema)
}

export async function fetchAiUsage(): Promise<AiUsage> {
  return parseResponse(await authFetch('/ai/usage'), aiUsageSchema)
}

export async function fetchAiSettings(): Promise<AiSettings> {
  return parseResponse(await authFetch('/ai/settings'), aiSettingsSchema)
}

export async function updateAiSettings(input: {
  dailyMessageCap?: number
  dailyCostCapUsd?: number
}): Promise<AiSettings> {
  return parseOrThrowApiError(
    await authFetch('/ai/settings', { method: 'PUT', body: JSON.stringify(input) }),
    aiSettingsSchema,
  )
}

/**
 * Ask one question.
 *
 * A refusal from the daily cap comes back as a **200** with `stopReason: 'cap_reached'`,
 * not an error status — §9.7 asks for a graceful message the person reads where they
 * asked, and an error status hands the UI an exception to render instead of an answer.
 */
export async function askAi(prompt: string): Promise<AiAnswer> {
  return parseOrThrowApiError(
    await authFetch('/ai/ask', { method: 'POST', body: JSON.stringify({ prompt }) }),
    aiAnswerSchema,
  )
}

/** A sub-cent cost rendered so it does not read as free. */
export function formatAiCost(costUsd: string): string {
  const value = Number(costUsd)
  if (!Number.isFinite(value)) return costUsd
  if (value === 0) return '$0.00'
  if (value < 0.01) return `<$0.01`
  return `$${value.toFixed(2)}`
}

// ---------------------------------------------------------------------------
// AI conversations, streaming chat and confirmation (Batch 31) — §9.2–§9.4
// ---------------------------------------------------------------------------

export async function fetchAiTools(): Promise<AiToolList> {
  return parseResponse(await authFetch('/ai/tools'), aiToolListSchema)
}

export async function fetchAiConversations(): Promise<AiConversationList> {
  return parseResponse(await authFetch('/ai/conversations'), aiConversationListSchema)
}

export async function createAiConversation(): Promise<AiConversation> {
  return parseOrThrowApiError(
    await authFetch('/ai/conversations', { method: 'POST' }),
    aiConversationSchema,
  )
}

export async function fetchAiConversation(id: string): Promise<AiConversationDetail> {
  return parseResponse(await authFetch(`/ai/conversations/${id}`), aiConversationDetailSchema)
}

export async function deleteAiConversation(id: string): Promise<void> {
  const response = await authFetch(`/ai/conversations/${id}`, { method: 'DELETE' })
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
}

/** One frame from the chat stream. `text` many times, then exactly one terminal event. */
export interface ChatStreamEvent {
  kind: 'text' | 'done' | 'confirm' | 'error'
  text: string
  toolCalls?: Array<{ id: string; toolName: string; input: Record<string, unknown> }>
}

/**
 * Read a `text/event-stream` body frame by frame.
 *
 * **Hand-rolled rather than `EventSource`,** which can only issue a bare GET — it cannot
 * POST the question and cannot carry the Authorization header. The buffering below is the
 * part that matters: a chunk boundary falls wherever the network puts it, so a frame
 * routinely arrives split across two reads and a parser that assumes one chunk is one
 * event drops text at random.
 */
export async function* readSse(response: Response): AsyncGenerator<ChatStreamEvent> {
  if (!response.ok || !response.body) {
    yield { kind: 'error', text: await errorMessage(response) }
    return
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let separator = buffer.indexOf('\n\n')
    while (separator !== -1) {
      const frame = buffer.slice(0, separator).trim()
      buffer = buffer.slice(separator + 2)
      if (frame.startsWith('data:')) {
        try {
          yield JSON.parse(frame.slice(5).trim()) as ChatStreamEvent
        } catch {
          // A malformed frame must not kill the stream — the rest of the answer is
          // still coming, and dropping one frame is far better than dropping the turn.
        }
      }
      separator = buffer.indexOf('\n\n')
    }
  }
}

/** Send a message and stream the reply. */
export async function* streamAiMessage(
  conversationId: string,
  prompt: string,
): AsyncGenerator<ChatStreamEvent> {
  const response = await authFetch(`/ai/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
  yield* readSse(response)
}

/**
 * §9.4 — answer a pending write, then stream whatever the assistant says next.
 *
 * Nothing has run when this is called: the write happens here if `confirm` is true, and
 * not at all if it is false.
 */
export async function* resolveAiToolCall(
  callId: string,
  confirm: boolean,
): AsyncGenerator<ChatStreamEvent> {
  const response = await authFetch(`/ai/tool-calls/${callId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ confirm }),
  })
  yield* readSse(response)
}

/** What §9.4's prompt says, in words rather than a tool name and a JSON blob. */
/** "2026-10-12" as "12 Oct 2026", the app's way of writing a date. */
function formatCardDate(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  if (!match) return iso
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${Number(match[3])} ${months[Number(match[2]) - 1] ?? match[2]} ${match[1]}`
}

export function describeToolCall(call: {
  toolName: string
  input: Record<string, unknown>
}): string {
  const input = call.input
  // Batch X7: the server settles the exact film before the card shows, and names it
  // with its year in `resolved.label`, so "Halloween" on the card is never a guess.
  const resolved = input.resolved
  const film =
    resolved && typeof resolved === 'object' && 'label' in resolved && typeof resolved.label === 'string'
      ? resolved.label
      : String(input.title)
  if (call.toolName === 'add_to_wanted') {
    const format = typeof input.preferredFormat === 'string' ? ` on ${formatLabel(input.preferredFormat) ?? input.preferredFormat}` : ''
    const price = typeof input.maxPrice === 'string' && input.maxPrice ? `, alerting below £${input.maxPrice}` : ''
    return `Add ${film} to the wanted list${format}${price}.`
  }
  if (call.toolName === 'log_watch') {
    const rating = typeof input.rating === 'number' ? `, rated ${input.rating}/5` : ''
    const when = typeof input.watchedAt === 'string' ? ` on ${formatCardDate(input.watchedAt)}` : ''
    return `Record that you watched ${film}${when}${rating}.`
  }
  return `Run ${call.toolName} with ${JSON.stringify(input)}.`
}

// ---------------------------------------------------------------------------
// Movie night (Batch 35) — §8.3, §8.4
// ---------------------------------------------------------------------------

export async function fetchMovieNights(): Promise<MovieNightSessionList> {
  return parseResponse(await authFetch('/movie-night'), movieNightSessionListSchema)
}

export async function createMovieNight(
  filters: Record<string, unknown> = {},
): Promise<MovieNightSession> {
  return parseOrThrowApiError(
    await authFetch('/movie-night', { method: 'POST', body: JSON.stringify({ filters }) }),
    movieNightSessionSchema,
  )
}

export async function joinMovieNight(inviteToken: string): Promise<MovieNightSession> {
  return parseOrThrowApiError(
    await authFetch(`/movie-night/join/${encodeURIComponent(inviteToken)}`, { method: 'POST' }),
    movieNightSessionSchema,
  )
}

export async function fetchMovieNight(id: string): Promise<MovieNightSession> {
  return parseResponse(await authFetch(`/movie-night/${id}`), movieNightSessionSchema)
}

/** Batch T4 — send tonight to the other person (everyone not in it, by default) as a push
 *  that opens it. One push per person per night; sending again changes nothing. */
export async function sendMovieNight(id: string, userIds?: string[]): Promise<MovieNightSession> {
  return parseOrThrowApiError(
    await authFetch(`/movie-night/${id}/send`, {
      method: 'POST',
      body: JSON.stringify(userIds ? { userIds } : {}),
    }),
    movieNightSessionSchema,
  )
}

export async function endMovieNight(id: string): Promise<MovieNightSession> {
  return parseOrThrowApiError(
    await authFetch(`/movie-night/${id}/end`, { method: 'POST' }),
    movieNightSessionSchema,
  )
}

export async function fetchMovieNightCandidates(id: string): Promise<MovieNightCandidateList> {
  return parseResponse(
    await authFetch(`/movie-night/${id}/candidates`),
    movieNightCandidateListSchema,
  )
}

export async function castMovieNightVote(
  id: string,
  suggestionId: string,
  liked: boolean,
): Promise<MovieNightVoteResult> {
  return parseOrThrowApiError(
    await authFetch(`/movie-night/${id}/votes`, {
      method: 'POST',
      body: JSON.stringify({ suggestionId, liked }),
    }),
    movieNightVoteResultSchema,
  )
}

/** Put a film forward — Batch S7, `DECISIONS.md` #157.
 *
 *  **Exactly one of `movieId` and `tmdbId`.** A film on the shelf reads its own metadata;
 *  one outside the Archive needs a title, because there is no row to read it from. */
export async function suggestMovieNightFilm(
  id: string,
  input: { movieId?: string; tmdbId?: number; title?: string; year?: number | null; posterPath?: string | null },
): Promise<MovieNightCandidateList> {
  return parseOrThrowApiError(
    await authFetch(`/movie-night/${id}/suggestions`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),
    movieNightCandidateListSchema,
  )
}

export interface MovieNightEvent {
  kind: 'vote' | 'match' | 'joined' | 'ended' | 'suggestion'
  sessionId: string
  movieId?: string
  title?: string
  posterPath?: string | null
}

/**
 * Watch a session's events — §8.4's realtime half, over `LISTEN`/`NOTIFY` and SSE.
 *
 * Same hand-rolled reader as the chat, for the same reason: `EventSource` cannot carry the
 * Authorization header. The heartbeat arrives as an SSE comment line (`: keep-alive`),
 * which has no `data:` prefix and is skipped here exactly as the spec intends.
 */
export async function* streamMovieNightEvents(
  id: string,
): AsyncGenerator<MovieNightEvent> {
  const response = await authFetch(`/movie-night/${id}/events`)
  if (!response.ok || !response.body) return
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let separator = buffer.indexOf('\n\n')
    while (separator !== -1) {
      const frame = buffer.slice(0, separator).trim()
      buffer = buffer.slice(separator + 2)
      if (frame.startsWith('data:')) {
        try {
          yield JSON.parse(frame.slice(5).trim()) as MovieNightEvent
        } catch {
          // One bad frame must not end the night.
        }
      }
      separator = buffer.indexOf('\n\n')
    }
  }
}

// ---------------------------------------------------------------------------
// Item photos (Batch 25) — §3.10
// ---------------------------------------------------------------------------

export async function fetchItemPhotos(itemId: string): Promise<ItemPhotoList> {
  return parseResponse(await authFetch(`/collection/${itemId}/photos`), itemPhotoListSchema)
}

/**
 * Upload one photo.
 *
 * No `Content-Type` is set: `authFetch` now omits its JSON default for a `FormData` body,
 * so the browser supplies `multipart/form-data` **with its boundary**. Writing that header
 * by hand omits the boundary, and the request then looks perfectly normal while the server
 * parses nothing out of it.
 */
export async function uploadItemPhoto(itemId: string, file: File): Promise<ItemPhoto> {
  const body = new FormData()
  body.append('file', file)
  return parseOrThrowApiError(
    await authFetch(`/collection/${itemId}/photos`, { method: 'POST', body }),
    itemPhotoSchema,
  )
}

export async function deleteItemPhoto(photoId: string): Promise<void> {
  const response = await authFetch(`/photos/${photoId}`, { method: 'DELETE' })
  if (!response.ok) throw new ApiError(await errorMessage(response), response.status)
}

/** The absolute URL for an image tag — the API origin, not the web app's. */
export function itemPhotoUrl(path: string): string {
  const base = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''
  return `${base}${path}`
}

// ---------------------------------------------------------------------------
// eBay (Batch 28) — §4.1, §4.3
// ---------------------------------------------------------------------------

/**
 * What a disc is currently being **asked** for on eBay UK.
 *
 * A POST rather than a GET, and not for tidiness: each call spends a unit of a finite
 * 5,000-a-day production quota, and a GET invites a prefetcher or a retry to spend it
 * again. Nothing here is a sold price — `basis` says so and every surface must show it.
 */
export async function fetchEbayPriceEstimate(input: {
  filmTitle: string
  formatCode?: string | null
  /** Sellers in this country only. `'GB'` by default at the server; `null` for anywhere. */
  country?: string | null
  /** Batch X6: a TV title, whose own "Complete Series" box sets are not another product. */
  isSeries?: boolean
}): Promise<EbayPriceEstimate> {
  return parseOrThrowApiError(
    await authFetch('/ebay/price-estimate', { method: 'POST', body: JSON.stringify(input) }),
    ebayPriceEstimateSchema,
  )
}

/**
 * A pre-filled link to eBay's "start your listing" form, and what to ask for the disc.
 *
 * Calling this creates nothing. Phase 4.3's preferred option — a Sell API draft listing —
 * describes something eBay does not do, so the app never holds a selling credential
 * (`DECISIONS.md` #142); the admin opens this signed in as themselves.
 */
export async function fetchEbayListingUrl(input: {
  filmTitle: string
  year?: number | null
  formatCode?: string | null
  condition?: string | null
  isSeries?: boolean
}): Promise<EbayListingUrl> {
  return parseOrThrowApiError(
    await authFetch('/ebay/listing-url', { method: 'POST', body: JSON.stringify(input) }),
    ebayListingUrlSchema,
  )
}

// ---------------------------------------------------------------------------
// Listing status (Batch 29) — §4.2, §4.4
// ---------------------------------------------------------------------------

export type ListingStatus = 'in_collection' | 'listed_for_sale' | 'sold' | 'donated'

/** How each state reads on screen. "Sold" and "Donated" are past tense on purpose: they
 *  describe something that already happened, not a state the disc is waiting in. */
export const LISTING_STATUS_LABELS: Record<ListingStatus, string> = {
  in_collection: 'On the shelf',
  listed_for_sale: 'Listed for sale',
  sold: 'Sold',
  donated: 'Donated',
}

/**
 * Move a disc between §3.4's listing states — one call for every transition.
 *
 * **Marking sold does not delete the disc.** The row stays, and the server's `owned_copy`
 * predicate is what removes it from the collection views — soft-deleting it instead would
 * hand it to §6.30's 90-day purge, which would destroy the record of what it fetched.
 *
 * Sending `in_collection` puts it back and clears the advert.
 */
export async function updateListingStatus(
  itemId: string,
  input: { status: ListingStatus; listingPrice?: string | null; ebayListingUrl?: string | null },
): Promise<CollectionItem> {
  return parseOrThrowApiError(
    await authFetch(`/collection/${itemId}/listing`, {
      method: 'PUT',
      body: JSON.stringify(input),
    }),
    collectionItemSchema,
  )
}

// ---------------------------------------------------------------------------
// Barcode scanning (Batch 24) — §3.3, §3.4
// ---------------------------------------------------------------------------

/**
 * Ask what a scanned barcode is — §3.4's cached mapping → collection → eBay → TMDB chain.
 *
 * **Nothing is added by calling this.** The response is candidates; §3.4's confirmation
 * step is mandatory because the batch's risk note expects a low hit rate on unknown discs
 * and wrong-edition matches. A code nothing matched comes back with an empty list and a
 * null `source`, which is an answer — the manual search — rather than an error.
 */
export async function lookupBarcode(barcode: string): Promise<BarcodeLookup> {
  return parseOrThrowApiError(
    await authFetch('/barcode/lookup', { method: 'POST', body: JSON.stringify({ barcode }) }),
    barcodeLookupSchema,
  )
}

/**
 * Record what the person decided the barcode is, so the next scan is instant.
 *
 * Adds no disc — that stays `addCollectionItem`, called with the confirmed film. Keeping
 * them apart means a confirmation that is right about the film and wrong about the shelf
 * does not have to be undone twice.
 */
export async function confirmBarcode(input: {
  barcode: string
  title: string
  source: Exclude<BarcodeCandidate['source'], 'cache'>
  movieId?: string | null
  tmdbId?: number | null
}): Promise<BarcodeLookup> {
  return parseOrThrowApiError(
    await authFetch('/barcode/confirm', { method: 'POST', body: JSON.stringify(input) }),
    barcodeLookupSchema,
  )
}

// ---------------------------------------------------------------------------
// Deals feed (Batch 22) — §5.9, §5.10
// ---------------------------------------------------------------------------

export interface DealFilters {
  retailer?: string | null
  genre?: string | null
  formatCode?: string | null
  minDiscount?: number | null
}

/** §5.10's filters. Dismissed deals are never returned and cannot be asked for — the
 *  acceptance is "dismissed items don't reappear", and a flag would be a way for them to. */
export async function fetchDeals(filters: DealFilters = {}): Promise<DealList> {
  const query = new URLSearchParams()
  if (filters.retailer) query.set('retailer', filters.retailer)
  if (filters.genre) query.set('genre', filters.genre)
  if (filters.formatCode) query.set('formatCode', filters.formatCode)
  if (filters.minDiscount) query.set('minDiscount', String(filters.minDiscount))
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return parseResponse(await authFetch(`/deals${suffix}`), dealListSchema)
}

/** Batch X2: what the daily check found, for Home's "Needs attention" row. Admin only. */
export async function fetchAttention(): Promise<Attention> {
  return parseResponse(await authFetch('/attention'), attentionSchema)
}

/** §5.10's one-tap dismiss, and its undo. A soft state, because tonight's scrape will
 *  re-find the same deal and the row has to remember. */
export async function dismissDeal(dealId: string, dismissed = true): Promise<Deal> {
  return parseOrThrowApiError(
    await authFetch(`/deals/${dealId}/dismiss`, {
      method: 'POST',
      body: JSON.stringify({ dismissed }),
    }),
    dealSchema,
  )
}

/** Dry by default, matching the endpoint — this hits real shops. */
export async function runDealsScrape(dryRun = true): Promise<DealsRun> {
  return parseOrThrowApiError(
    await authFetch(`/deals/scrape?dryRun=${String(dryRun)}`, { method: 'POST' }),
    dealsRunSchema,
  )
}
