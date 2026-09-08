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
