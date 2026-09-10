import { z } from 'zod'

// Shared response schemas land with their endpoints. Health is the only Batch 1
// application endpoint; domain schemas arrive with the read surface in Batch 5.
export const healthResponseSchema = z.object({
  status: z.literal('ok'),
  commitSha: z.string().min(1),
})

// ---------------------------------------------------------------------------
// Auth (Batch 3)
//
// Schemas ship with their endpoint. A schema added later never gets added
// (`DECISIONS.md` #6), so every auth response the web app reads is parsed here.
// ---------------------------------------------------------------------------

export const userRoleSchema = z.enum(['admin', 'viewer'])

export const tokenPairSchema = z.object({
  accessToken: z.string().min(1),
  refreshToken: z.string().min(1),
  tokenType: z.literal('bearer'),
  expiresIn: z.number().int().positive(),
})

export const profileResponseSchema = z.object({
  id: z.string().uuid(),
  displayName: z.string().min(1),
  role: userRoleSchema,
  // False for a profile seeded with `pin_hash = NULL` — no credential yet, which is
  // not the same as a blank one.
  hasPin: z.boolean(),
  // Batch 9. A boolean on the wire though the column is a timestamp: the client's only
  // question is whether to show the wizard.
  onboardingCompleted: z.boolean(),
})

export const apiErrorSchema = z.object({
  detail: z.string().optional(),
  error: z.string().optional(),
})

// ---------------------------------------------------------------------------
// Collection read + identify surface (Batch 5)
// ---------------------------------------------------------------------------

export const genreSchema = z.object({
  id: z.number().int().positive(),
  name: z.string().min(1),
})

export const castMemberSchema = z.object({
  personName: z.string().min(1),
  tmdbPersonId: z.number().int().positive().nullable(),
  characterName: z.string().nullable(),
  profilePath: z.string().nullable(),
})

export const crewMemberSchema = z.object({
  personName: z.string().min(1),
  tmdbPersonId: z.number().int().positive().nullable(),
  role: z.enum(['director', 'writer', 'producer', 'composer']),
})

export const locationSchema = z.object({
  section: z.string().nullable(),
  shelf: z.string().nullable(),
  // Composed by the API so all three collection views say "Front 2nd" identically.
  label: z.string().min(1),
})

export const movieListItemSchema = z.object({
  id: z.string().uuid(),
  title: z.string().min(1),
  originalTitle: z.string().nullable(),
  year: z.number().int().nullable(),
  posterPath: z.string().nullable(),
  backdropPath: z.string().nullable(),
  tmdbRating: z.number().min(0).max(10).nullable(),
  runtimeMinutes: z.number().int().nonnegative().nullable(),
  bestFormatOwned: z.string().nullable(),
  bestHdrOwned: z.string().nullable(),
  bestAudioOwned: z.string().nullable(),
  identified: z.boolean(),
  copyCount: z.number().int().positive(),
  locations: z.array(locationSchema),
  watched: z.boolean(),
})

export const moviePageSchema = z.object({
  items: z.array(movieListItemSchema),
  totalMovies: z.number().int().nonnegative(),
  totalItems: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  perPage: z.number().int().positive(),
  pages: z.number().int().nonnegative(),
})

export const movieDetailSchema = movieListItemSchema.extend({
  imdbId: z.string().nullable(),
  overview: z.string().nullable(),
  tagline: z.string().nullable(),
  genres: z.array(genreSchema),
  cast: z.array(castMemberSchema),
  crew: z.array(crewMemberSchema),
  trailerKey: z.string().nullable(),
  letterboxdSlug: z.string().nullable(),
  mediaType: z.string().nullable(),
})

export const collectionCopySchema = z.object({
  id: z.string().uuid(),
  formats: z.array(z.string()),
  location: z.string().nullable(),
  section: z.string().nullable(),
  shelf: z.string().nullable(),
  subCategory: z.string().nullable(),
  notes: z.string().nullable(),
  purchasePrice: z.string().nullable(),
  purchaseSource: z.string().nullable(),
  purchaseDate: z.string().nullable(),
  condition: z.string().nullable(),
  hasPlaybackIssues: z.boolean(),
  playbackNotes: z.string().nullable(),
  videoSpecs: z.record(z.unknown()).nullable(),
  audioSpecs: z.array(z.record(z.unknown())).nullable(),
  specialFeatures: z.array(z.string()).nullable(),
  regionCode: z.string().nullable(),
  releaseLabel: z.string().nullable(),
  listingStatus: z.string(),
  // Batch 8: the version an edit is based on. Sent back as `baseUpdatedAt` so a queued
  // offline edit cannot overwrite a change made after it.
  updatedAt: z.string(),
})

export const collectionCopiesSchema = z.array(collectionCopySchema)

export const searchResponseSchema = z.object({
  items: z.array(movieListItemSchema),
  query: z.string(),
  total: z.number().int().nonnegative(),
})

export const candidateSchema = z.object({
  tmdbId: z.number().int().positive(),
  title: z.string().min(1),
  year: z.number().int().nullable(),
  overview: z.string(),
  posterPath: z.string().nullable(),
  confidence: z.number().min(0).max(1),
  titleSimilarity: z.number().min(0).max(1),
})

export const candidateListSchema = z.object({
  movieId: z.string().uuid(),
  title: z.string().min(1),
  query: z.string().min(1),
  candidates: z.array(candidateSchema).max(5),
})

// ---------------------------------------------------------------------------
// Location facets and watch log (Batch 6)
// ---------------------------------------------------------------------------

export const shelfFacetSchema = z.object({
  shelf: z.string().min(1),
  movieCount: z.number().int().nonnegative(),
  itemCount: z.number().int().nonnegative(),
})

export const sectionFacetSchema = z.object({
  section: z.string().min(1),
  movieCount: z.number().int().nonnegative(),
  itemCount: z.number().int().nonnegative(),
  shelves: z.array(shelfFacetSchema),
})

export const decadeFacetSchema = z.object({
  decade: z.number().int(),
  movieCount: z.number().int().nonnegative(),
})

export const collectionFacetsSchema = z.object({
  sections: z.array(sectionFacetSchema),
  unsectionedItemCount: z.number().int().nonnegative(),
  decades: z.array(decadeFacetSchema),
  undatedMovieCount: z.number().int().nonnegative(),
})

export const watchLogEntrySchema = z.object({
  id: z.string().uuid(),
  movieId: z.string().uuid(),
  movieTitle: z.string().min(1),
  posterPath: z.string().nullable(),
  watchedAt: z.string(),
  isRewatch: z.boolean(),
  // §3.7's half-star scale, deliberately not TMDB's 0–10.
  personalRating: z.number().min(0.5).max(5).nullable(),
  review: z.string().nullable(),
})

export const watchLogPageSchema = z.object({
  items: z.array(watchLogEntrySchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  perPage: z.number().int().positive(),
  pages: z.number().int().nonnegative(),
})

// ---------------------------------------------------------------------------
// On-this-day memories and rewatch suggestions (Batch 37)
// ---------------------------------------------------------------------------

export const onThisDayMemorySchema = z.object({
  id: z.string().uuid(),
  movieId: z.string().uuid(),
  movieTitle: z.string().min(1),
  posterPath: z.string().nullable(),
  watchedAt: z.string(),
  yearsAgo: z.number().int().positive(),
  personalRating: z.number().min(0.5).max(5).nullable(),
})

export const onThisDayMemoriesSchema = z.array(onThisDayMemorySchema)

export const rewatchSuggestionSchema = z.object({
  movieId: z.string().uuid(),
  movieTitle: z.string().min(1),
  posterPath: z.string().nullable(),
  lastWatchedAt: z.string(),
  personalRating: z.number().min(0.5).max(5),
})

export const rewatchSuggestionsSchema = z.array(rewatchSuggestionSchema)

export type UserRole = z.infer<typeof userRoleSchema>
export type TokenPair = z.infer<typeof tokenPairSchema>
export type ProfileResponse = z.infer<typeof profileResponseSchema>
export type Genre = z.infer<typeof genreSchema>
export type CastMember = z.infer<typeof castMemberSchema>
export type CrewMember = z.infer<typeof crewMemberSchema>
export type MovieListItem = z.infer<typeof movieListItemSchema>
export type MoviePage = z.infer<typeof moviePageSchema>
export type MovieDetail = z.infer<typeof movieDetailSchema>
export type CollectionCopy = z.infer<typeof collectionCopySchema>
export type SearchResponse = z.infer<typeof searchResponseSchema>
export type Candidate = z.infer<typeof candidateSchema>
export type CandidateList = z.infer<typeof candidateListSchema>
export type MovieLocation = z.infer<typeof locationSchema>
export type ShelfFacet = z.infer<typeof shelfFacetSchema>
export type SectionFacet = z.infer<typeof sectionFacetSchema>
export type DecadeFacet = z.infer<typeof decadeFacetSchema>
export type CollectionFacets = z.infer<typeof collectionFacetsSchema>
export type WatchLogEntry = z.infer<typeof watchLogEntrySchema>
export type WatchLogPage = z.infer<typeof watchLogPageSchema>
export type OnThisDayMemory = z.infer<typeof onThisDayMemorySchema>
export type RewatchSuggestion = z.infer<typeof rewatchSuggestionSchema>

// ---------------------------------------------------------------------------
// Write surface (Batch 7) — §3.1, §3.2, §3.5, §3.11
//
// Admin-only, every one of them. Schemas ship with their endpoint, so the add
// form, the trash and the audit log are all parsed rather than cast.
// ---------------------------------------------------------------------------

/** The vocabularies the API enforces. Mirrored here so a form cannot offer a value a
 *  CHECK constraint would then reject. */
export const conditionSchema = z.enum(['new', 'like_new', 'good', 'acceptable', 'damaged'])
export const formatCodeSchema = z.enum(['4k_uhd', 'blu_ray', 'dvd', 'download'])
export const duplicateReasonSchema = z.enum(['another_copy', 'upgrade'])
export const auditActionSchema = z.enum(['create', 'update', 'delete', 'restore', 'bulk_import'])

export const collectionItemSchema = z.object({
  id: z.string().uuid(),
  movieId: z.string().uuid(),
  movieTitle: z.string().min(1),
  formats: z.array(z.string()),
  location: z.string().nullable(),
  section: z.string().nullable(),
  shelf: z.string().nullable(),
  // Composed server-side, like `locationSchema.label`, so every surface says it identically.
  locationLabel: z.string().min(1),
  subCategory: z.string().nullable(),
  notes: z.string().nullable(),
  condition: z.string().nullable(),
  conditionUpdatedAt: z.string().nullable(),
  hasPlaybackIssues: z.boolean(),
  playbackNotes: z.string().nullable(),
  // A string, not a number: a price is money and must not round-trip through a float.
  purchasePrice: z.string().nullable(),
  purchaseSource: z.string().nullable(),
  purchaseDate: z.string().nullable(),
  listingStatus: z.string(),
  updatedAt: z.string(),
  deletedAt: z.string().nullable(),
})

export const existingCopySchema = z.object({
  id: z.string().uuid(),
  formats: z.array(z.string()),
  locationLabel: z.string().min(1),
  condition: z.string().nullable(),
})

export const duplicateCheckSchema = z.object({
  movieId: z.string().uuid().nullable(),
  movieTitle: z.string().nullable(),
  isDuplicate: z.boolean(),
  existingCopies: z.array(existingCopySchema),
  // Decided by the API against the same format ranking the database enforces, rather
  // than re-derived here where it could disagree with `bestFormatOwned`.
  isUpgrade: z.boolean(),
  bestFormatOwned: z.string().nullable(),
})

export const tmdbSearchResultSchema = z.object({
  tmdbId: z.number().int().positive(),
  title: z.string().min(1),
  year: z.number().int().nullable(),
  overview: z.string(),
  posterPath: z.string().nullable(),
  inCollection: z.boolean(),
  movieId: z.string().uuid().nullable(),
})

export const tmdbSearchResponseSchema = z.object({
  query: z.string(),
  results: z.array(tmdbSearchResultSchema),
})

export const trashItemSchema = z.object({
  id: z.string().uuid(),
  targetTable: z.string().min(1),
  movieId: z.string().uuid(),
  movieTitle: z.string().min(1),
  posterPath: z.string().nullable(),
  formats: z.array(z.string()),
  locationLabel: z.string().min(1),
  deletedAt: z.string(),
})

export const trashPageSchema = z.object({
  items: z.array(trashItemSchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  perPage: z.number().int().positive(),
  pages: z.number().int().nonnegative(),
})

/** One field's movement, as `diff_snapshots` writes it. The values are deliberately
 *  `unknown`: a diff spans booleans, strings, arrays and nulls, and pretending
 *  otherwise would make the schema reject a correct row. */
export const auditFieldChangeSchema = z.object({
  from: z.unknown(),
  to: z.unknown(),
})

export const auditEntrySchema = z.object({
  id: z.string().uuid(),
  actorId: z.string().uuid().nullable(),
  // Null when the profile is gone. The row outlives it (`DECISIONS.md` #5), so the log
  // still says what happened even when it can no longer say who.
  actorName: z.string().nullable(),
  actionType: auditActionSchema,
  targetTable: z.string().min(1),
  targetId: z.string().min(1),
  changes: z.record(z.unknown()).nullable(),
  createdAt: z.string(),
})

export const auditPageSchema = z.object({
  items: z.array(auditEntrySchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  perPage: z.number().int().positive(),
  pages: z.number().int().nonnegative(),
})

export type Condition = z.infer<typeof conditionSchema>
export type FormatCode = z.infer<typeof formatCodeSchema>
export type DuplicateReason = z.infer<typeof duplicateReasonSchema>
export type AuditAction = z.infer<typeof auditActionSchema>
export type CollectionItem = z.infer<typeof collectionItemSchema>
export type ExistingCopy = z.infer<typeof existingCopySchema>
export type DuplicateCheck = z.infer<typeof duplicateCheckSchema>
export type TmdbSearchResult = z.infer<typeof tmdbSearchResultSchema>
export type TmdbSearchResponse = z.infer<typeof tmdbSearchResponseSchema>
export type TrashItem = z.infer<typeof trashItemSchema>
export type TrashPage = z.infer<typeof trashPageSchema>
export type AuditFieldChange = z.infer<typeof auditFieldChangeSchema>
export type AuditEntry = z.infer<typeof auditEntrySchema>
export type AuditPage = z.infer<typeof auditPageSchema>

// ---------------------------------------------------------------------------
// Box sets and smart collections (Batch 12) — §11.3, §11.4, §11.5
//
// Schemas ship with their endpoint (`DECISIONS.md` #6). The filter vocabulary below
// is the one place the web app, the API's `SmartCollectionFilters` and `GET /movies`
// all have to agree; keeping it a real schema rather than `z.record(z.unknown())` is
// what makes a typo in a saved filter a parse error instead of a silently ignored key.
// ---------------------------------------------------------------------------

export const smartCollectionIconSchema = z.enum([
  'sparkles',
  'star',
  'heart',
  'clapperboard',
  'disc',
  'eye',
  'flame',
  'bookmark',
  'layers',
])

export const collectionSortSchema = z.enum(['title', 'year', 'rating'])
export const collectionSortOrderSchema = z.enum(['asc', 'desc'])

export const smartCollectionFiltersSchema = z.object({
  genreId: z.number().int().positive().nullable(),
  year: z.number().int().nullable(),
  format: z.string().nullable(),
  section: z.string().nullable(),
  shelf: z.string().nullable(),
  decadeFrom: z.number().int().nullable(),
  decadeTo: z.number().int().nullable(),
  minRating: z.number().min(0).max(10).nullable(),
  watched: z.boolean().nullable(),
})

export const smartCollectionSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  icon: smartCollectionIconSchema,
  filters: smartCollectionFiltersSchema,
  sortBy: collectionSortSchema,
  sortOrder: collectionSortOrderSchema,
  isPinned: z.boolean(),
  displayOrder: z.number().int().nonnegative(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export const smartCollectionListSchema = z.object({
  items: z.array(smartCollectionSchema),
  total: z.number().int().nonnegative(),
})

/** The same `items` shape as `moviePageSchema`, so the results page reuses the grid
 *  rather than growing a second card that renders the same film differently. */
export const smartCollectionResultsSchema = z.object({
  collection: smartCollectionSchema,
  items: z.array(movieListItemSchema),
  totalMovies: z.number().int().nonnegative(),
  totalItems: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  perPage: z.number().int().positive(),
  pages: z.number().int().nonnegative(),
})

export const boxSetSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  label: z.string().nullable(),
  volumeNumber: z.number().int().positive().nullable(),
  seriesId: z.string().uuid().nullable(),
  seriesName: z.string().nullable(),
  expectedCount: z.number().int().positive().nullable(),
  posterUrl: z.string().nullable(),
  notes: z.string().nullable(),
  ownedCount: z.number().int().nonnegative(),
  /** Deliberately three-valued. `null` means nobody recorded how big the box is — not
   *  that it is incomplete, which would put a permanent red mark against every set an
   *  admin never filled in. */
  isComplete: z.boolean().nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export const boxSetMemberSchema = z.object({
  collectionItemId: z.string().uuid(),
  movieId: z.string().uuid(),
  movieTitle: z.string().min(1),
  posterPath: z.string().nullable(),
  year: z.number().int().nullable(),
  formats: z.array(z.string()),
  locationLabel: z.string().min(1),
  discNumber: z.number().int().positive().nullable(),
})

export const boxSetDetailSchema = boxSetSchema.extend({
  items: z.array(boxSetMemberSchema),
  volumes: z.array(boxSetSchema),
})

export const boxSetListSchema = z.object({
  items: z.array(boxSetSchema),
  total: z.number().int().nonnegative(),
})

export type SmartCollectionIcon = z.infer<typeof smartCollectionIconSchema>
export type CollectionSort = z.infer<typeof collectionSortSchema>
export type CollectionSortOrder = z.infer<typeof collectionSortOrderSchema>
export type SmartCollectionFilters = z.infer<typeof smartCollectionFiltersSchema>
export type SmartCollection = z.infer<typeof smartCollectionSchema>
export type SmartCollectionList = z.infer<typeof smartCollectionListSchema>
export type SmartCollectionResults = z.infer<typeof smartCollectionResultsSchema>
export type BoxSet = z.infer<typeof boxSetSchema>
export type BoxSetMember = z.infer<typeof boxSetMemberSchema>
export type BoxSetDetail = z.infer<typeof boxSetDetailSchema>
export type BoxSetList = z.infer<typeof boxSetListSchema>

// ---------------------------------------------------------------------------
// Completion insights (Batch 13) — §3.15, §11.1, §11.2
// ---------------------------------------------------------------------------

export const completionSetTypeSchema = z.enum([
  'director',
  'actor',
  'franchise',
  'box_set',
  'award',
  'curated_list',
])

/** One film in a set. `movieId` is null exactly when the film is missing — a missing film
 *  has no row in this database, which is what "missing" means, so its title and poster
 *  come from the set's cached member list rather than from `movies`. */
export const completionFilmSchema = z.object({
  tmdbId: z.number().int().positive(),
  title: z.string().min(1),
  year: z.number().int().nullable(),
  posterPath: z.string().nullable(),
  owned: z.boolean(),
  movieId: z.string().uuid().nullable(),
})

export const completionSetSchema = z.object({
  id: z.string().uuid(),
  setType: completionSetTypeSchema,
  setKey: z.string().min(1),
  setName: z.string().min(1),
  ownedCount: z.number().int().nonnegative(),
  totalCount: z.number().int().nonnegative(),
  missingCount: z.number().int().nonnegative(),
  // Computed server-side so the bar's width and the "12 of 61" beside it cannot disagree.
  percentComplete: z.number().int().min(0).max(100),
  lastRefreshed: z.string().nullable(),
})

export const completionSetDetailSchema = completionSetSchema.extend({
  films: z.array(completionFilmSchema),
})

export const completionInsightsSchema = z.object({
  items: z.array(completionSetSchema),
  total: z.number().int().nonnegative(),
  // The oldest `lastRefreshed` of any set: a page is only as current as its stalest row.
  oldestRefresh: z.string().nullable(),
})

export const completionRefreshSchema = z.object({
  created: z.number().int().nonnegative(),
  updated: z.number().int().nonnegative(),
  unchanged: z.number().int().nonnegative(),
  skipped: z.number().int().nonnegative(),
  total: z.number().int().nonnegative(),
  errors: z.array(z.string()),
  dryRun: z.boolean(),
})

export type CompletionSetType = z.infer<typeof completionSetTypeSchema>
export type CompletionFilm = z.infer<typeof completionFilmSchema>
export type CompletionSet = z.infer<typeof completionSetSchema>
export type CompletionSetDetail = z.infer<typeof completionSetDetailSchema>
export type CompletionInsights = z.infer<typeof completionInsightsSchema>
export type CompletionRefresh = z.infer<typeof completionRefreshSchema>

// ---------------------------------------------------------------------------
// Stats, activity and export (Batch 14) — §13.1–13.4
// ---------------------------------------------------------------------------

export const countSliceSchema = z.object({
  key: z.string().min(1),
  label: z.string().min(1),
  itemCount: z.number().int().nonnegative(),
  movieCount: z.number().int().nonnegative(),
})

export const decadeSliceSchema = z.object({
  decade: z.number().int(),
  label: z.string().min(1),
  movieCount: z.number().int().nonnegative(),
})

export const watchedFilmSchema = z.object({
  movieId: z.string().uuid(),
  title: z.string().min(1),
  posterPath: z.string().nullable(),
  watchCount: z.number().int().positive(),
  lastWatched: z.string().nullable(),
})

/** Money in integer pence. A running total built from floats drifts. */
export const spendPointSchema = z.object({
  month: z.string().min(1),
  spentCents: z.number().int(),
  cumulativeCents: z.number().int(),
  itemCount: z.number().int().nonnegative(),
})

export const statsSchema = z.object({
  totalMovies: z.number().int().nonnegative(),
  totalItems: z.number().int().nonnegative(),
  identifiedMovies: z.number().int().nonnegative(),
  watchedMovies: z.number().int().nonnegative(),
  formats: z.array(countSliceSchema),
  genres: z.array(countSliceSchema),
  decades: z.array(decadeSliceSchema),
  sections: z.array(countSliceSchema),
  mostWatched: z.array(watchedFilmSchema),
  spendOverTime: z.array(spendPointSchema),
  /** The denominator that lets an empty `spendOverTime` say *why* it is empty: no prices
   *  recorded, rather than nothing bought. */
  itemsWithPrice: z.number().int().nonnegative(),
})

export const activityKindSchema = z.enum(['added', 'watched', 'edited', 'removed', 'restored'])

export const activityEventSchema = z.object({
  id: z.string().min(1),
  kind: activityKindSchema,
  at: z.string(),
  actorName: z.string().nullable(),
  movieId: z.string().uuid().nullable(),
  movieTitle: z.string().nullable(),
  posterPath: z.string().nullable(),
  detail: z.string().nullable(),
})

export const activitySchema = z.object({
  items: z.array(activityEventSchema),
  total: z.number().int().nonnegative(),
})

export type CountSlice = z.infer<typeof countSliceSchema>
export type DecadeSlice = z.infer<typeof decadeSliceSchema>
export type WatchedFilm = z.infer<typeof watchedFilmSchema>
export type SpendPoint = z.infer<typeof spendPointSchema>
export type Stats = z.infer<typeof statsSchema>
export type ActivityKind = z.infer<typeof activityKindSchema>
export type ActivityEvent = z.infer<typeof activityEventSchema>
export type Activity = z.infer<typeof activitySchema>

// ---------------------------------------------------------------------------
// Trash, audit filters and lending (Batch 15) — §13.5, §13.6, §12.5
// ---------------------------------------------------------------------------

export const trashTableSchema = z.enum([
  'collection_items',
  'watch_log',
  'movies',
  'box_sets',
  // Batch 18. Batch 15 deliberately left these out rather than answering an empty page
  // for tables that did not exist; they exist now.
  'wanted_list',
  'retailers',
  // Batch 27. A revoked gift link is soft-deleted, so restoring brings the **same slug**
  // back and a link already shared with family keeps working.
  'gift_links',
])

export const trashCountSchema = z.object({
  table: trashTableSchema,
  count: z.number().int().nonnegative(),
})

/** One deleted row, in a shape that reads the same whatever table it came from — so the
 *  trash is one list rather than four components maintaining one idea. */
export const trashRowSchema = z.object({
  id: z.string().uuid(),
  table: trashTableSchema,
  label: z.string().min(1),
  sublabel: z.string().nullable(),
  posterPath: z.string().nullable(),
  movieId: z.string().uuid().nullable(),
  deletedAt: z.string(),
})

export const trashListSchema = z.object({
  items: z.array(trashRowSchema),
  total: z.number().int().nonnegative(),
  page: z.number().int().positive(),
  perPage: z.number().int().positive(),
  pages: z.number().int().nonnegative(),
  counts: z.array(trashCountSchema),
})

export const purgePreviewSchema = z.object({
  table: trashTableSchema,
  olderThanDays: z.number().int().positive(),
  count: z.number().int().nonnegative(),
  dryRun: z.boolean(),
  deleted: z.number().int().nonnegative(),
})

export const loanSchema = z.object({
  id: z.string().uuid(),
  collectionItemId: z.string().uuid(),
  movieId: z.string().uuid(),
  movieTitle: z.string().min(1),
  posterPath: z.string().nullable(),
  formats: z.array(z.string()),
  locationLabel: z.string().min(1),
  borrowerName: z.string().min(1),
  lentDate: z.string(),
  dueDate: z.string().nullable(),
  returnedDate: z.string().nullable(),
  /** Derived server-side from the due date and today, never stored: a stored flag needs a
   *  job to keep it true and is wrong between runs. */
  isOverdue: z.boolean(),
  /** Negative when overdue. Null when no due date was set — "no deadline" is not "due
   *  today", and rendering it as 0 would put every open-ended loan in the red. */
  daysUntilDue: z.number().int().nullable(),
  notes: z.string().nullable(),
})

export const loanListSchema = z.object({
  items: z.array(loanSchema),
  total: z.number().int().nonnegative(),
  openCount: z.number().int().nonnegative(),
  overdueCount: z.number().int().nonnegative(),
})

export type TrashTable = z.infer<typeof trashTableSchema>
export type TrashCount = z.infer<typeof trashCountSchema>
export type TrashRow = z.infer<typeof trashRowSchema>
export type TrashList = z.infer<typeof trashListSchema>
export type PurgePreview = z.infer<typeof purgePreviewSchema>
export type Loan = z.infer<typeof loanSchema>
export type LoanList = z.infer<typeof loanListSchema>

// ---------------------------------------------------------------------------
// Streaming and recommendations (Batch 16) — §7.1, §7.2
// ---------------------------------------------------------------------------

export const offerKindSchema = z.enum(['flatrate', 'rent', 'buy'])

/** Three states since Batch 18 built §3.5's `wanted_list`. Batch 16 shipped two, because
 *  a `wanted` badge that could never appear would have been a legend entry pointing at
 *  nothing — this is the third state arriving with the table behind it. */
export const ownershipStateSchema = z.enum(['owned', 'wanted', 'unowned'])

export const streamingOfferSchema = z.object({
  providerId: z.number().int().positive(),
  providerName: z.string().min(1),
  logoPath: z.string().nullable(),
  kind: offerKindSchema,
})

export const streamingSchema = z.object({
  movieId: z.string().uuid(),
  region: z.string().length(2),
  link: z.string().nullable(),
  offers: z.array(streamingOfferSchema),
  /** True when the film has no TMDB id, so nothing could be looked up — distinct from
   *  "TMDB knows it and has no offers", which is a real answer. */
  unidentified: z.boolean(),
  /** True when TMDB could not be reached. A flag rather than a 5xx, because the client
   *  treats any 5xx as a *network* failure — so a 502 here would blame the reader's
   *  connection for TMDB being down. */
  unavailable: z.boolean(),
})

export const recommendationSchema = z.object({
  tmdbId: z.number().int().positive(),
  title: z.string().min(1),
  year: z.number().int().nullable(),
  overview: z.string(),
  posterPath: z.string().nullable(),
  ownership: ownershipStateSchema,
  movieId: z.string().uuid().nullable(),
})

export const recommendationListSchema = z.object({
  movieId: z.string().uuid(),
  items: z.array(recommendationSchema),
  ownedCount: z.number().int().nonnegative(),
  // Required, not `.default(false)`: the API always sends it (pydantic serialises a
  // defaulted field), and a zod default makes the parsed type optional, which then leaks
  // `boolean | undefined` into every consumer.
  unavailable: z.boolean(),
})

export const newReleaseSchema = z.object({
  tmdbId: z.number().int().positive(),
  title: z.string().min(1),
  releaseDate: z.string().nullable(),
  posterPath: z.string().nullable(),
  overview: z.string(),
  matchedGenres: z.array(z.string()),
  ownership: ownershipStateSchema,
  movieId: z.string().uuid().nullable(),
})

export const newReleaseListSchema = z.object({
  items: z.array(newReleaseSchema),
  basedOnGenres: z.array(z.string()),
})

export type OfferKind = z.infer<typeof offerKindSchema>
export type OwnershipState = z.infer<typeof ownershipStateSchema>
export type StreamingOffer = z.infer<typeof streamingOfferSchema>
export type Streaming = z.infer<typeof streamingSchema>
export type Recommendation = z.infer<typeof recommendationSchema>
export type RecommendationList = z.infer<typeof recommendationListSchema>
export type NewRelease = z.infer<typeof newReleaseSchema>
export type NewReleaseList = z.infer<typeof newReleaseListSchema>

// ---------------------------------------------------------------------------
// Release calendar and iCal feed (Batch 17) — §3.26, §7.3, §7.4
// ---------------------------------------------------------------------------

export const releaseTypeSchema = z.enum([
  '4k_uhd_release',
  'blu_ray_release',
  'streaming_release',
  'theatrical',
  'award_ceremony',
  'sale_event',
])

export const calendarEntrySchema = z.object({
  id: z.string().uuid(),
  title: z.string().min(1),
  releaseType: releaseTypeSchema,
  typeLabel: z.string().min(1),
  releaseDate: z.string(),
  label: z.string().nullable(),
  region: z.string().length(2),
  url: z.string().nullable(),
  posterPath: z.string().nullable(),
  overview: z.string().nullable(),
  movieId: z.string().uuid().nullable(),
})

/** Bucketed by day server-side, so the grid is a rendering problem and an empty month is
 *  an explicit empty map rather than something the client infers. */
export const calendarMonthSchema = z.object({
  month: z.string(),
  days: z.record(z.array(calendarEntrySchema)),
  total: z.number().int().nonnegative(),
})

export const calendarListSchema = z.object({
  items: z.array(calendarEntrySchema),
  total: z.number().int().nonnegative(),
})

/** A path, not a URL: the API cannot know its own public origin without trusting the
 *  `Host` header, so the web app composes the absolute URL from `VITE_API_URL`. */
export const calendarSubscriptionSchema = z.object({
  path: z.string().min(1),
  createdAt: z.string(),
  replacedPrevious: z.boolean(),
})

export const calendarIngestSchema = z.object({
  created: z.number().int().nonnegative(),
  updated: z.number().int().nonnegative(),
  unchanged: z.number().int().nonnegative(),
  skipped: z.number().int().nonnegative(),
  total: z.number().int().nonnegative(),
  errors: z.array(z.string()),
  dryRun: z.boolean(),
})

export type ReleaseType = z.infer<typeof releaseTypeSchema>
export type CalendarEntry = z.infer<typeof calendarEntrySchema>
export type CalendarMonth = z.infer<typeof calendarMonthSchema>
export type CalendarListing = z.infer<typeof calendarListSchema>
export type CalendarSubscription = z.infer<typeof calendarSubscriptionSchema>
export type CalendarIngest = z.infer<typeof calendarIngestSchema>

// ---------------------------------------------------------------------------
// Wanted list and retailers (Batch 18) — §3.5, §3.16, §5.1, §5.2
// ---------------------------------------------------------------------------

export const wantedItemSchema = z.object({
  id: z.string().uuid(),
  movieId: z.string().uuid(),
  movieTitle: z.string().min(1),
  year: z.number().int().nullable(),
  posterPath: z.string().nullable(),
  preferredFormat: z.string().nullable(),
  /** Which edition within that format — "Arte Originale Slipcover", "Steelbook". Free
   *  text, because boutique edition names are invented per release. */
  preferredEdition: z.string().nullable(),
  /** A string, not a number: money must not round-trip through a float, and this is the
   *  threshold Batch 20's price alerts compare against. */
  maxPrice: z.string().nullable(),
  currency: z.string().length(3),
  /** "Still looking" — a decision. Distinct from `deleted_at`, which is an accident. */
  isActive: z.boolean(),
  notes: z.string().nullable(),
  /** Wanting a film you own is not an error — a DVD-to-4K upgrade is exactly that. */
  ownedAlready: z.boolean(),
  addedAt: z.string(),
})

export const wantedListSchema = z.object({
  items: z.array(wantedItemSchema),
  total: z.number().int().nonnegative(),
  activeCount: z.number().int().nonnegative(),
})

export const scraperTypeSchema = z.enum(['built_in', 'generic_css', 'custom'])
export const scrapeFrequencySchema = z.enum(['daily', 'weekly', 'manual'])

export const retailerSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  baseUrl: z.string().min(1),
  dealsUrl: z.string().nullable(),
  searchUrlTemplate: z.string().nullable(),
  scraperType: scraperTypeSchema,
  scraperConfig: z.record(z.unknown()),
  scrapeFrequency: scrapeFrequencySchema,
  enabled: z.boolean(),
  currency: z.string().length(3),
  region: z.string().length(2),
  notes: z.string().nullable(),
  lastScrapedAt: z.string().nullable(),
  lastScrapeStatus: z.string().nullable(),
  lastScrapeError: z.string().nullable(),
  consecutiveFailures: z.number().int().nonnegative(),
  /** False until Batch 19 gives this retailer selectors — so the page can say "not
   *  configured" rather than implying a working scraper exists. */
  isConfigured: z.boolean(),
  addedAt: z.string(),
})

export const retailerListSchema = z.object({
  items: z.array(retailerSchema),
  total: z.number().int().nonnegative(),
  enabledCount: z.number().int().nonnegative(),
  configuredCount: z.number().int().nonnegative(),
})

export const retailerSeedSchema = z.object({
  created: z.number().int().nonnegative(),
  existing: z.number().int().nonnegative(),
  names: z.array(z.string()),
})

export type WantedItem = z.infer<typeof wantedItemSchema>
export type WantedList = z.infer<typeof wantedListSchema>
export type ScraperType = z.infer<typeof scraperTypeSchema>
export type ScrapeFrequency = z.infer<typeof scrapeFrequencySchema>
export type RetailerRow = z.infer<typeof retailerSchema>
export type RetailerList = z.infer<typeof retailerListSchema>
export type RetailerSeed = z.infer<typeof retailerSeedSchema>

// ---------------------------------------------------------------------------
// Scraper framework (Batch 19) — §5.3, §5.4
// ---------------------------------------------------------------------------

/** What §5.4's "test scraper" found, and whether it looks like a price.
 *
 *  `ok` is **not** "the request succeeded" — a page that fetched perfectly and yielded a
 *  plausible wrong number reports `ok: false` with reasons. That distinction is the whole
 *  reason the tool exists before a retailer is enabled. */
export const scraperTestSchema = z.object({
  fetched: z.boolean(),
  finalUrl: z.string().nullable(),
  title: z.string().nullable(),
  rawPriceText: z.string().nullable(),
  price: z.string().nullable(),
  currency: z.string().nullable(),
  listingUrl: z.string().nullable(),
  ok: z.boolean(),
  reasons: z.array(z.string()),
  error: z.string().nullable(),
})

export const builtInScraperSchema = z.object({
  name: z.string().min(1),
  searchUrlTemplate: z.string().min(1),
  scraperConfig: z.record(z.unknown()),
  /** True only after a permitted live check. A selector nobody has run is a guess. */
  verified: z.boolean(),
  note: z.string().nullable(),
})

export const builtInScraperListSchema = z.object({
  items: z.array(builtInScraperSchema),
  unverified: z.array(z.string()),
})

export const scrapeOutcomeSchema = z.object({
  retailer: z.string().min(1),
  wantedTitle: z.string().min(1),
  ok: z.boolean(),
  price: z.string().nullable(),
  /** The currency `price` was read in. Never converted (`DECISIONS.md` #79), so a report
   *  showing the number must show this beside it rather than assuming pounds. */
  currency: z.string().nullable(),
  /** The format actually priced, set only when it is not the one wanted. A fallback is
   *  allowed but never silent: a `maxPrice` alert compares against whatever was priced. */
  substitutedFormat: z.string().nullable(),
  /** False only when the wanted edition was not on the shelf and a different one was
   *  priced; null when the want named no edition. */
  editionMatched: z.boolean().nullable(),
  /** Nothing was attempted — these shops sell discs and the want is for a digital copy.
   *  Neither a success nor a failure, and not counted towards auto-disable. */
  skipped: z.boolean(),
  /** The shop was asked, answered with real listings, and has not got this film. Also
   *  neither a success nor a failure — a boutique label that does not carry a blockbuster
   *  has not broken, and must not be switched off for saying so. */
  notStocked: z.boolean(),
  url: z.string().nullable(),
  reasons: z.array(z.string()),
  error: z.string().nullable(),
})

export const scrapeRunSchema = z.object({
  outcomes: z.array(scrapeOutcomeSchema),
  succeeded: z.number().int().nonnegative(),
  failed: z.number().int().nonnegative(),
  skipped: z.number().int().nonnegative(),
  notStocked: z.number().int().nonnegative(),
  /** Wants whose shop answered with an empty results page — neither a failure nor a
   *  claim the shop has not got it (`DECISIONS.md` #125).
   *
   *  **Optional, not defaulted.** `.default()` leaves the *input* type optional, which
   *  the response parser then cannot assign; and optional is the honest shape anyway —
   *  an API deployed a minute before the web app does not send this field, and a run row
   *  that fails to parse is a worse outcome than one missing a count. Read it as
   *  `?? 0`. */
  noResults: z.number().int().nonnegative().optional(),
  written: z.number().int().nonnegative(),
  disabled: z.array(z.string()),
  dryRun: z.boolean(),
})

export type ScraperTest = z.infer<typeof scraperTestSchema>
export type BuiltInScraper = z.infer<typeof builtInScraperSchema>
export type BuiltInScraperList = z.infer<typeof builtInScraperListSchema>
export type ScrapeOutcome = z.infer<typeof scrapeOutcomeSchema>
export type ScrapeRun = z.infer<typeof scrapeRunSchema>

// ---------------------------------------------------------------------------
// Gift links (Batch 27) — §3.21, §6.26, §12.1, §12.2
// ---------------------------------------------------------------------------

export const giftFilterConfigSchema = z.object({
  // Nullable rather than defaulted: a zod `.default()` makes the *parsed* type optional,
  // which leaks `| undefined` into every consumer. The API always sends both fields.
  maxPrice: z.string().nullable(),
  formats: z.array(z.string()),
})

/** The **admin** view: slug, counts, provenance. */
export const giftLinkSchema = z.object({
  id: z.string().uuid(),
  slug: z.string().min(16),
  path: z.string().min(1),
  title: z.string().min(1),
  filterConfig: giftFilterConfigSchema,
  expiresAt: z.string().nullable(),
  viewCount: z.number().int().nonnegative(),
  lastViewedAt: z.string().nullable(),
  isActive: z.boolean(),
  isUsable: z.boolean(),
  createdAt: z.string(),
})

export const giftLinkListSchema = z.object({
  items: z.array(giftLinkSchema),
  total: z.number().int().nonnegative(),
})

export const giftRetailerLinkSchema = z.object({
  name: z.string().min(1),
  url: z.string().min(1),
})

/** One film on the **public** page.
 *
 *  Deliberately **not** an extension of any admin type. Nothing here says whether the
 *  recipient already owns the film, what they have watched, or who they are — and keeping
 *  the two schemas unrelated is what stops a field added to one leaking through the other. */
export const giftFilmSchema = z.object({
  title: z.string().min(1),
  year: z.number().int().nullable(),
  posterPath: z.string().nullable(),
  preferredFormat: z.string().nullable(),
  maxPrice: z.string().nullable(),
  currency: z.string().length(3),
  retailerLinks: z.array(giftRetailerLinkSchema),
})

export const giftPageSchema = z.object({
  title: z.string().min(1),
  films: z.array(giftFilmSchema),
  total: z.number().int().nonnegative(),
  filterConfig: giftFilterConfigSchema,
})

export type GiftFilterConfig = z.infer<typeof giftFilterConfigSchema>
export type GiftLink = z.infer<typeof giftLinkSchema>
export type GiftLinkList = z.infer<typeof giftLinkListSchema>
export type GiftFilm = z.infer<typeof giftFilmSchema>
export type GiftPage = z.infer<typeof giftPageSchema>

// ---------------------------------------------------------------------------
// Notifications and push (Batch 11) — §6.1, §6.2, §5.11
// ---------------------------------------------------------------------------

/** The application server's public key, for `pushManager.subscribe`.
 *
 *  `configured: false` is a first-class answer, not an error. It is the state the app was
 *  in for TMDB for an unknown length of time behind a fully green gate — a feature simply
 *  absent from the deployment, with the front end unable to say so. Here the UI can. */
export const vapidKeySchema = z.object({
  publicKey: z.string().nullable(),
  configured: z.boolean(),
})

/** One registered device.
 *
 *  There is no `endpoint` field and there must never be one: the endpoint is a bearer
 *  capability — anyone holding it can push to that device — and the UI only needs enough
 *  to tell two rows apart. */
export const pushSubscriptionSchema = z.object({
  id: z.string().uuid(),
  deviceLabel: z.string().nullable(),
  endpointPreview: z.string().min(1),
  pushService: z.string().min(1),
  userAgent: z.string().nullable(),
  createdAt: z.string(),
  lastUsedAt: z.string().nullable(),
  failureCount: z.number().int().nonnegative(),
})

export const pushSubscriptionListSchema = z.object({
  items: z.array(pushSubscriptionSchema),
  total: z.number().int().nonnegative(),
})

export const notificationPreferenceSchema = z.object({
  dealsEnabled: z.boolean(),
  saleEventsEnabled: z.boolean(),
  releasesEnabled: z.boolean(),
  loansEnabled: z.boolean(),
  movieNightEnabled: z.boolean(),
  digestMode: z.boolean(),
  digestHourLocal: z.number().int().min(0).max(23),
  quietHoursStart: z.string().nullable(),
  quietHoursEnd: z.string().nullable(),
  quietHoursTimezone: z.string().min(1),
})

export const notificationSchema = z.object({
  id: z.string().uuid(),
  category: z.string().min(1),
  status: z.enum(['queued', 'sent', 'suppressed', 'failed']),
  title: z.string().min(1),
  body: z.string(),
  url: z.string().nullable(),
  createdAt: z.string(),
  deliverAfter: z.string().nullable(),
  deferredReason: z.string().nullable(),
  suppressedReason: z.string().nullable(),
  sentAt: z.string().nullable(),
  deliveredCount: z.number().int().nonnegative(),
})

export const notificationListSchema = z.object({
  items: z.array(notificationSchema),
  total: z.number().int().nonnegative(),
  queuedCount: z.number().int().nonnegative(),
})

/** What the test button did.
 *
 *  `delivered` separates "I pressed test and nothing happened" into three different
 *  problems: no devices, the push service refused, or it was delivered and the browser
 *  chose not to show it. */
export const testNotificationSchema = z.object({
  notificationId: z.string().uuid(),
  delivered: z.number().int().nonnegative(),
  devicesTried: z.number().int().nonnegative(),
  subscriptionsRemoved: z.number().int().nonnegative(),
  status: z.enum(['queued', 'sent', 'suppressed', 'failed']),
  suppressedReason: z.string().nullable(),
})

export const reminderRunSchema = z.object({
  asOf: z.string(),
  seasonsSeeded: z.number().int().nonnegative(),
  saleEvents: z.number().int().nonnegative(),
  releases: z.number().int().nonnegative(),
  overdueLoans: z.number().int().nonnegative(),
  queued: z.number().int().nonnegative(),
  delivered: z.number().int().nonnegative(),
})

export type VapidKey = z.infer<typeof vapidKeySchema>
export type PushSubscriptionRecord = z.infer<typeof pushSubscriptionSchema>
export type PushSubscriptionList = z.infer<typeof pushSubscriptionListSchema>
export type NotificationPreference = z.infer<typeof notificationPreferenceSchema>
export type NotificationRecord = z.infer<typeof notificationSchema>
export type NotificationList = z.infer<typeof notificationListSchema>
export type TestNotificationResult = z.infer<typeof testNotificationSchema>
export type ReminderRun = z.infer<typeof reminderRunSchema>

// ---------------------------------------------------------------------------
// Daily scraping, drop alerts and the roll-up (Batch 20) — §5.5, §5.6, §5.8
// ---------------------------------------------------------------------------

/** One recorded scrape run.
 *
 *  `attempted` minus `notStocked` is the denominator `DECISIONS.md` #112's corrected §5.5
 *  criterion compares `written` against. A shop that answered honestly and has not got the
 *  film is neither a gap nor a failure (#107), which is why it has its own count. */
export const scrapeRunRecordSchema = z.object({
  id: z.string().uuid(),
  startedAt: z.string(),
  finishedAt: z.string().nullable(),
  trigger: z.enum(['cron', 'manual']),
  dryRun: z.boolean(),
  attempted: z.number().int().nonnegative(),
  notStocked: z.number().int().nonnegative(),
  noResults: z.number().int().nonnegative().optional(),
  skipped: z.number().int().nonnegative(),
  succeeded: z.number().int().nonnegative(),
  failed: z.number().int().nonnegative(),
  written: z.number().int().nonnegative(),
  alertsQueued: z.number().int().nonnegative(),
  failures: z.array(z.record(z.string())),
  disabledRetailers: z.array(z.string()),
  error: z.string().nullable(),
})

export const scrapeRunListSchema = z.object({
  items: z.array(scrapeRunRecordSchema),
  total: z.number().int().nonnegative(),
})

export const aggregationSchema = z.object({
  daysAggregated: z.number().int().nonnegative(),
  rowsWritten: z.number().int().nonnegative(),
  rowsMerged: z.number().int().nonnegative(),
  rawRowsRemoved: z.number().int().nonnegative(),
})

export const dailyRunSchema = z.object({
  runId: z.string().uuid(),
  written: z.number().int().nonnegative(),
  attempted: z.number().int().nonnegative(),
  notStocked: z.number().int().nonnegative(),
  noResults: z.number().int().nonnegative().optional(),
  skipped: z.number().int().nonnegative(),
  succeeded: z.number().int().nonnegative(),
  failed: z.number().int().nonnegative(),
  alertsQueued: z.number().int().nonnegative(),
  pushesSent: z.number().int().nonnegative(),
  disabledRetailers: z.array(z.string()),
  failures: z.array(z.record(z.string())),
  aggregation: aggregationSchema.nullable(),
  dryRun: z.boolean(),
})

export type ScrapeRunRecord = z.infer<typeof scrapeRunRecordSchema>
export type ScrapeRunList = z.infer<typeof scrapeRunListSchema>
export type Aggregation = z.infer<typeof aggregationSchema>
export type DailyRun = z.infer<typeof dailyRunSchema>

// ---------------------------------------------------------------------------
// AI assistant — client and caps (Batch 30) — §9.1, §9.7
// ---------------------------------------------------------------------------

/** Whether the assistant works in **this** deployment.
 *
 *  `configured: false` is a first-class answer. `ANTHROPIC_API_KEY` lives only in a Railway
 *  variable, and the TMDB outage is what a missing one looks like when nothing in the code
 *  can observe its absence. */
export const aiStatusSchema = z.object({
  configured: z.boolean(),
  model: z.string().min(1),
})

/** An answer, with what producing it cost.
 *
 *  `costUsd` is a **string** because it is a decimal: a short question costs a fraction of
 *  a penny and a float would not round to what was billed. */
export const aiAnswerSchema = z.object({
  id: z.string().uuid(),
  text: z.string(),
  model: z.string().min(1),
  inputTokens: z.number().int().nonnegative(),
  outputTokens: z.number().int().nonnegative(),
  cacheReadTokens: z.number().int().nonnegative(),
  cacheWriteTokens: z.number().int().nonnegative(),
  costUsd: z.string(),
  stopReason: z.string().nullable(),
  latencyMs: z.number().int().nonnegative(),
  error: z.string().nullable(),
})

export const aiUsageSchema = z.object({
  messages: z.number().int().nonnegative(),
  messageCap: z.number().int().nonnegative(),
  messagesRemaining: z.number().int().nonnegative(),
  costUsd: z.string(),
  costCapUsd: z.string(),
  blocked: z.boolean(),
  limitMessage: z.string().nullable(),
  resetsAt: z.string(),
})

export const aiSettingsSchema = z.object({
  dailyMessageCap: z.number().int().nonnegative(),
  dailyCostCapUsd: z.string(),
})

export type AiStatus = z.infer<typeof aiStatusSchema>
export type AiAnswer = z.infer<typeof aiAnswerSchema>
export type AiUsage = z.infer<typeof aiUsageSchema>
export type AiSettings = z.infer<typeof aiSettingsSchema>

// ---------------------------------------------------------------------------
// AI conversations, tools and confirmation (Batch 31) — §9.2, §9.3, §9.4
// ---------------------------------------------------------------------------

export const aiToolSummarySchema = z.object({
  name: z.string().min(1),
  description: z.string(),
  /** Whether using it changes something — and therefore whether it will ask first. */
  writes: z.boolean(),
})

export const aiToolListSchema = z.object({
  role: z.string().min(1),
  items: z.array(aiToolSummarySchema),
  total: z.number().int().nonnegative(),
})

export const aiConversationSchema = z.object({
  id: z.string().uuid(),
  title: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export const aiConversationListSchema = z.object({
  items: z.array(aiConversationSchema),
  total: z.number().int().nonnegative(),
})

export const aiChatMessageSchema = z.object({
  id: z.string().uuid(),
  role: z.string().min(1),
  text: z.string(),
  sequence: z.number().int().positive(),
  createdAt: z.string(),
})

/** A write Claude asked for and has **not** performed.
 *
 *  `input` is carried in full because §9.4's prompt has to say what will actually happen —
 *  "Claude wants to use a tool" is not a decision anyone can make. */
export const aiPendingToolCallSchema = z.object({
  id: z.string().uuid(),
  toolName: z.string().min(1),
  input: z.record(z.unknown()),
})

export const aiConversationDetailSchema = aiConversationSchema.extend({
  messages: z.array(aiChatMessageSchema),
  pendingToolCalls: z.array(aiPendingToolCallSchema),
})

export type AiToolSummary = z.infer<typeof aiToolSummarySchema>
export type AiToolList = z.infer<typeof aiToolListSchema>
export type AiConversation = z.infer<typeof aiConversationSchema>
export type AiConversationList = z.infer<typeof aiConversationListSchema>
export type AiChatMessage = z.infer<typeof aiChatMessageSchema>
export type AiPendingToolCall = z.infer<typeof aiPendingToolCallSchema>
export type AiConversationDetail = z.infer<typeof aiConversationDetailSchema>

// ---------------------------------------------------------------------------
// Movie night (Batch 35) — §8.3, §8.4
// ---------------------------------------------------------------------------

/** One sitting.
 *
 *  `inviteToken` comes back only to people already in the session — it is the whole
 *  credential for joining, the same as Batch 27's gift slug. */
export const movieNightSessionSchema = z.object({
  id: z.string().uuid(),
  status: z.enum(['open', 'ended']),
  filters: z.record(z.unknown()),
  inviteToken: z.string().min(16),
  invitePath: z.string().min(1),
  participantCount: z.number().int().positive(),
  createdAt: z.string(),
  endedAt: z.string().nullable(),
})

export const movieNightSessionListSchema = z.object({
  items: z.array(movieNightSessionSchema),
  total: z.number().int().nonnegative(),
})

export const movieNightCandidateSchema = z.object({
  movieId: z.string().uuid(),
  title: z.string().min(1),
  year: z.number().int().nullable(),
  posterPath: z.string().nullable(),
  overview: z.string().nullable(),
})

export const movieNightCandidateListSchema = z.object({
  items: z.array(movieNightCandidateSchema),
  total: z.number().int().nonnegative(),
})

export const movieNightMatchSchema = z.object({
  movieId: z.string().uuid(),
  title: z.string().min(1),
  posterPath: z.string().nullable(),
})

export const movieNightVoteResultSchema = z.object({
  recorded: z.boolean(),
  /** Non-null only on the swipe that *completes* a match. */
  match: movieNightMatchSchema.nullable(),
})

export type MovieNightSession = z.infer<typeof movieNightSessionSchema>
export type MovieNightSessionList = z.infer<typeof movieNightSessionListSchema>
export type MovieNightCandidate = z.infer<typeof movieNightCandidateSchema>
export type MovieNightCandidateList = z.infer<typeof movieNightCandidateListSchema>
export type MovieNightMatch = z.infer<typeof movieNightMatchSchema>
export type MovieNightVoteResult = z.infer<typeof movieNightVoteResultSchema>

// ---------------------------------------------------------------------------
// Item photos (Batch 25) — §3.10
// ---------------------------------------------------------------------------

/** One photo's metadata.
 *
 *  There is no `data` field and there must never be one: a five-photo gallery as base64
 *  would be about a megabyte of JSON re-sent on every render. The browser fetches `url`,
 *  which is a cacheable image with a strong `ETag`. */
export const itemPhotoSchema = z.object({
  id: z.string().uuid(),
  url: z.string().min(1),
  caption: z.string().nullable(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
  byteSize: z.number().int().positive(),
  position: z.number().int().nonnegative(),
  createdAt: z.string(),
})

export const itemPhotoListSchema = z.object({
  items: z.array(itemPhotoSchema),
  total: z.number().int().nonnegative(),
  /** How many more §3.10's five-per-item ceiling allows. */
  remaining: z.number().int().nonnegative(),
})

export type ItemPhoto = z.infer<typeof itemPhotoSchema>
export type ItemPhotoList = z.infer<typeof itemPhotoListSchema>
