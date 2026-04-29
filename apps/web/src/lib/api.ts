const BASE = '/api/v1'

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

export const FORMATS = ['4K UHD', 'Blu-ray', 'DVD'] as const
