import { X } from 'lucide-react'
import { FORMATS, TMDB_GENRES, type MovieFilters } from '@/lib/api'

interface Props {
  filters: MovieFilters
  total: number
  onChange: (f: MovieFilters) => void
}

const SELECT_CLS =
  'h-8 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring'

const currentYear = new Date().getFullYear()
const YEARS: number[] = []
for (let y = currentYear; y >= 1970; y--) YEARS.push(y)

export function FilterBar({ filters, total, onChange }: Props) {
  const hasFilters = !!(filters.genreId || filters.year || filters.format)

  function clear() {
    onChange({})
  }

  return (
    <div className="flex flex-wrap items-center gap-2 px-4 py-2.5 border-b border-border bg-background/80 backdrop-blur-sm">
      {/* Genre */}
      <select
        className={SELECT_CLS}
        value={filters.genreId ?? ''}
        onChange={(e) =>
          onChange({ ...filters, genreId: e.target.value ? Number(e.target.value) : undefined })
        }
        aria-label="Filter by genre"
      >
        <option value="">All genres</option>
        {TMDB_GENRES.map((g) => (
          <option key={g.id} value={g.id}>
            {g.name}
          </option>
        ))}
      </select>

      <select
        className={SELECT_CLS}
        value={`${filters.sort ?? 'title'}:${filters.order ?? 'asc'}`}
        onChange={(e) => {
          const [sort, order] = e.target.value.split(':') as [
            NonNullable<MovieFilters['sort']>,
            NonNullable<MovieFilters['order']>,
          ]
          onChange({ ...filters, sort, order })
        }}
        aria-label="Sort movies"
      >
        <option value="title:asc">Title A–Z</option>
        <option value="title:desc">Title Z–A</option>
        <option value="year:desc">Newest first</option>
        <option value="year:asc">Oldest first</option>
        <option value="rating:desc">Highest rated</option>
      </select>

      {/* Format */}
      <select
        className={SELECT_CLS}
        value={filters.format ?? ''}
        onChange={(e) => onChange({ ...filters, format: e.target.value || undefined })}
        aria-label="Filter by format"
      >
        <option value="">All formats</option>
        {FORMATS.map((f) => (
          <option key={f.value} value={f.value}>
            {f.label}
          </option>
        ))}
      </select>

      {/* Year */}
      <select
        className={SELECT_CLS}
        value={filters.year ?? ''}
        onChange={(e) =>
          onChange({ ...filters, year: e.target.value ? Number(e.target.value) : undefined })
        }
        aria-label="Filter by year"
      >
        <option value="">All years</option>
        {YEARS.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>

      {/* Clear */}
      {hasFilters && (
        <button
          onClick={clear}
          className="flex items-center gap-1 h-8 px-2.5 rounded-md text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <X size={12} />
          Clear
        </button>
      )}

      {/* Count */}
      <span className="ml-auto text-xs text-muted-foreground tabular-nums">
        {total.toLocaleString()} {total === 1 ? 'movie' : 'movies'}
      </span>
    </div>
  )
}
