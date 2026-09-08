import {
  apiErrorSchema,
  candidateListSchema,
  collectionCopiesSchema,
  movieDetailSchema,
  moviePageSchema,
  searchResponseSchema,
  type CandidateList,
  type CollectionCopy,
  type MovieDetail,
  type MoviePage,
  type SearchResponse,
} from '@mcu/shared'
import type { ZodType } from 'zod'

import { authFetch } from './auth-tokens'

export type {
  Candidate,
  CandidateList,
  CollectionCopy,
  MovieDetail,
  MovieListItem,
  MoviePage,
  SearchResponse,
} from '@mcu/shared'

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

export interface MovieFilters {
  genreId?: number
  year?: number
  format?: string
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
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.order) params.set('order', filters.order)

  return parseResponse(await authFetch(`/movies?${params}`), moviePageSchema)
}

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
