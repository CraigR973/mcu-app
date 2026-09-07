import { API_BASE, authFetch } from './auth-tokens'

const BASE = API_BASE

// Batch 3 replaced Supabase sessions with PIN + JWT. `authFetch` attaches the bearer
// token and retries once through a refresh, so callers here are unchanged.
const authedFetch = authFetch

export interface MovieListItem {
  id: number
  title: string
  original_title: string | null
  release_date: string | null
  runtime: number | null
  popularity: number | null
  vote_average: number | null
  vote_count: number | null
  poster_path: string | null
  backdrop_path: string | null
  genre_ids: number[] | null
  best_format_owned: string | null
  best_hdr_owned: string | null
  best_audio_owned: string | null
}

export interface MovieListResponse {
  data: MovieListItem[]
  meta: {
    total: number
    page: number
    per_page: number
    pages: number
  }
}

export interface MovieFilters {
  genre_id?: number
  year?: number
  format?: string
  page?: number
  per_page?: number
  sort?: string
  order?: 'asc' | 'desc'
}

export async function fetchMovies(filters: MovieFilters = {}): Promise<MovieListResponse> {
  const params = new URLSearchParams()
  if (filters.genre_id) params.set('genre_id', String(filters.genre_id))
  if (filters.year) params.set('year', String(filters.year))
  if (filters.format) params.set('format', filters.format)
  if (filters.page) params.set('page', String(filters.page))
  if (filters.per_page) params.set('per_page', String(filters.per_page))
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.order) params.set('order', filters.order)

  const res = await fetch(`${BASE}/movies?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<MovieListResponse>
}

export interface CreditOut {
  person_id: number | null
  person_name: string | null
  credit_type: string
  character: string | null
  department: string | null
  job: string | null
  credit_order: number | null
  profile_path: string | null
}

export interface MovieDetail extends MovieListItem {
  overview: string | null
  tagline: string | null
  status: string | null
  budget: number | null
  revenue: number | null
  imdb_id: string | null
  homepage: string | null
  cast: CreditOut[]
  crew: CreditOut[]
}

export interface MovieDetailResponse {
  data: MovieDetail
}

export async function fetchMovie(id: number): Promise<MovieDetailResponse> {
  const res = await fetch(`${BASE}/movies/${id}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<MovieDetailResponse>
}

export interface CollectionItemOut {
  id: number
  format: string
  edition: string | null
  condition: string
  region: string | null
  purchase_price: string | null
  purchase_date: string | null
  purchase_source: string | null
  notes: string | null
  resolution: string | null
  hdr_format: string | null
  audio_formats: string[] | null
  is_for_sale: boolean
}

export async function fetchCopies(movieId: number): Promise<CollectionItemOut[]> {
  const res = await fetch(`${BASE}/movies/${movieId}/copies`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<CollectionItemOut[]>
}

export function backdropUrl(path: string | null, size = 'w1280'): string {
  if (!path) return ''
  return `https://image.tmdb.org/t/p/${size}${path}`
}

export interface SearchResultItem {
  id: number
  title: string
  original_title: string | null
  poster_path: string | null
  release_date: string | null
  vote_average: number | null
  best_format_owned: string | null
}

export interface SearchResponse {
  data: SearchResultItem[]
  query: string
  total: number
}

export async function fetchSearch(q: string, limit = 20): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) })
  const res = await fetch(`${BASE}/search?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<SearchResponse>
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
  { value: '4k_bluray', label: '4K UHD' },
  { value: 'bluray',    label: 'Blu-ray' },
  { value: 'dvd',       label: 'DVD' },
] as const

export const FORMAT_COLORS: Record<string, string> = {
  '4k_bluray': 'bg-blue-900 text-blue-200',
  'bluray':    'bg-indigo-900 text-indigo-200',
  'dvd':       'bg-slate-700 text-slate-300',
}

export function formatLabel(value: string | null): string | null {
  if (!value) return null
  return FORMATS.find(f => f.value === value)?.label ?? value
}

// ---------- TMDB search (admin only) ----------

export interface TMDBSearchResult {
  id: number
  title: string
  release_date: string | null
  poster_path: string | null
  overview: string | null
  vote_average: number | null
}

export interface TMDBSearchResponse {
  results: TMDBSearchResult[]
  total_results: number
  page: number
}

export async function tmdbSearch(q: string, year?: number): Promise<TMDBSearchResponse> {
  const params = new URLSearchParams({ q })
  if (year) params.set('year', String(year))
  const res = await authedFetch(`${BASE}/tmdb/search?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<TMDBSearchResponse>
}

// ---------- Add to collection (admin only) ----------

export interface CollectionItemCreate {
  tmdb_id: number
  format: string
  condition: string
  edition?: string
  purchase_price?: string
  purchase_date?: string
  purchase_source?: string
  notes?: string
}

export interface AddToCollectionResponse {
  data: CollectionItemOut
  movie_id: number
  duplicate_warning: boolean
  existing_formats: string[]
}

export async function addToCollection(body: CollectionItemCreate): Promise<AddToCollectionResponse> {
  const res = await authedFetch(`${BASE}/collection`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new Error(err.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<AddToCollectionResponse>
}

export const ALL_FORMATS = [
  { value: '4k_bluray', label: '4K UHD Blu-ray' },
  { value: 'bluray',    label: 'Blu-ray' },
  { value: 'dvd',       label: 'DVD' },
  { value: 'digital',   label: 'Digital' },
  { value: 'laserdisc', label: 'Laserdisc' },
  { value: 'vhs',       label: 'VHS' },
  { value: 'hddvd',     label: 'HD DVD' },
] as const

export const CONDITIONS = [
  { value: 'sealed',    label: 'Sealed' },
  { value: 'mint',      label: 'Mint' },
  { value: 'very_good', label: 'Very Good' },
  { value: 'good',      label: 'Good' },
  { value: 'fair',      label: 'Fair' },
  { value: 'poor',      label: 'Poor' },
] as const
