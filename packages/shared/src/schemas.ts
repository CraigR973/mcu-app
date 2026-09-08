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
