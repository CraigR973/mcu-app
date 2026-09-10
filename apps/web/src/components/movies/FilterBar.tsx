import { X } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchFacets,
  FORMATS,
  MIN_RATING_OPTIONS,
  TMDB_GENRES,
  type MovieFilters,
} from '@/lib/api'
import { cn } from '@/lib/utils'

interface Props {
  filters: MovieFilters
  total: number
  onChange: (f: MovieFilters) => void
}

const SELECT_CLS =
  'h-8 rounded-md border border-input bg-background px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring'

function decadeLabel(decade: number): string {
  return `${decade}s`
}

/** §3.9's filter panel, as data. The phase names these four by example. */
const SPEC_TOGGLES: Array<{
  label: string
  isActive: (filters: MovieFilters) => boolean
  apply: (active: boolean) => Partial<MovieFilters>
}> = [
  {
    label: 'Dolby Vision',
    isActive: (filters) => filters.hdr === 'Dolby Vision',
    apply: (active) => ({ hdr: active ? undefined : 'Dolby Vision' }),
  },
  {
    label: 'Dolby Atmos',
    isActive: (filters) => filters.audio === 'Dolby Atmos',
    apply: (active) => ({ audio: active ? undefined : 'Dolby Atmos' }),
  },
  {
    label: 'Region-free',
    isActive: (filters) => filters.regionFree === true,
    apply: (active) => ({ regionFree: active ? undefined : true }),
  },
]

export function FilterBar({ filters, total, onChange }: Props) {
  // The section, shelf and decade vocabularies come from the collection itself. A
  // hard-coded year list is what hid 47% of this collection before Batch 6: it started
  // at 1970, and 517 of the 1,085 dated films are older than that.
  const { data: facets } = useQuery({
    queryKey: ['collection-facets'],
    queryFn: fetchFacets,
    staleTime: 30 * 60 * 1000,
  })

  const sections = facets?.sections ?? []
  const decades = facets?.decades ?? []
  const selectedSection = sections.find((s) => s.section === filters.section)
  const shelves = selectedSection?.shelves ?? []

  const hasFilters = !!(
    filters.genreId ||
    filters.year ||
    filters.format ||
    filters.section ||
    filters.shelf ||
    filters.decadeFrom ||
    filters.decadeTo ||
    filters.minRating != null ||
    filters.watched != null ||
    filters.hdr ||
    filters.audio ||
    filters.regionFree
  )

  function clear() {
    onChange({})
  }

  return (
    <div className="flex flex-wrap items-center gap-2 px-4 py-2.5 border-b border-border bg-background/80 backdrop-blur-sm">
      {/* Section */}
      <select
        className={SELECT_CLS}
        value={filters.section ?? ''}
        onChange={(e) =>
          // Changing section clears the shelf: "Front 2nd" then "Digital" would
          // otherwise ask for a shelf the digital library does not have and return
          // nothing, which reads as a bug rather than an impossible question.
          onChange({ ...filters, section: e.target.value || undefined, shelf: undefined })
        }
        aria-label="Filter by section"
      >
        <option value="">Anywhere</option>
        {sections.map((section) => (
          <option key={section.section} value={section.section}>
            {section.section} ({section.itemCount})
          </option>
        ))}
      </select>

      {/* Shelf — only offered for a section that has shelves */}
      {shelves.length > 0 && (
        <select
          className={SELECT_CLS}
          value={filters.shelf ?? ''}
          onChange={(e) => onChange({ ...filters, shelf: e.target.value || undefined })}
          aria-label="Filter by shelf"
        >
          <option value="">All shelves</option>
          {shelves.map((shelf) => (
            <option key={shelf.shelf} value={shelf.shelf}>
              {shelf.shelf} shelf ({shelf.itemCount})
            </option>
          ))}
        </select>
      )}

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

      {/* Decade range */}
      <div className="flex items-center gap-1">
        <select
          className={SELECT_CLS}
          value={filters.decadeFrom ?? ''}
          onChange={(e) =>
            onChange({
              ...filters,
              decadeFrom: e.target.value ? Number(e.target.value) : undefined,
            })
          }
          aria-label="Earliest decade"
        >
          <option value="">Any decade</option>
          {decades.map((d) => (
            <option key={d.decade} value={d.decade}>
              {decadeLabel(d.decade)} ({d.movieCount})
            </option>
          ))}
        </select>
        <span className="text-xs text-muted-foreground">to</span>
        <select
          className={SELECT_CLS}
          value={filters.decadeTo ?? ''}
          onChange={(e) =>
            onChange({
              ...filters,
              decadeTo: e.target.value ? Number(e.target.value) : undefined,
            })
          }
          aria-label="Latest decade"
        >
          <option value="">Now</option>
          {decades.map((d) => (
            <option key={d.decade} value={d.decade}>
              {decadeLabel(d.decade)}
            </option>
          ))}
        </select>
      </div>

      {/* Rating */}
      <select
        className={SELECT_CLS}
        value={filters.minRating ?? ''}
        onChange={(e) =>
          onChange({
            ...filters,
            minRating: e.target.value ? Number(e.target.value) : undefined,
          })
        }
        aria-label="Minimum TMDB rating"
      >
        <option value="">Any rating</option>
        {MIN_RATING_OPTIONS.map((rating) => (
          <option key={rating} value={rating}>
            {rating}+
          </option>
        ))}
      </select>

      {/* Watched */}
      <select
        className={SELECT_CLS}
        value={filters.watched === undefined ? '' : String(filters.watched)}
        onChange={(e) =>
          onChange({
            ...filters,
            watched: e.target.value === '' ? undefined : e.target.value === 'true',
          })
        }
        aria-label="Filter by watched status"
      >
        <option value="">Watched or not</option>
        <option value="true">Watched</option>
        <option value="false">Not watched</option>
      </select>

      {/* Sort */}
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

      {/* §3.9's spec filters — "Dolby Atmos only", "Dolby Vision 4K only", "Region-free".
          Toggles rather than selects: each is one thing somebody wants to see, and a
          dropdown of one useful value per category is three clicks for what should be one.

          **They are only useful once specs have been fetched.** Until then every one of
          them returns nothing, which is honest — the app does not know a disc is Dolby
          Vision until Blu-ray.com has said so. */}
      {SPEC_TOGGLES.map((toggle) => {
        const active = toggle.isActive(filters)
        return (
          <button
            key={toggle.label}
            type="button"
            aria-pressed={active}
            onClick={() => onChange({ ...filters, ...toggle.apply(active) })}
            className={cn(
              'h-8 rounded-md border px-2.5 text-xs transition-colors',
              active
                ? 'border-primary bg-primary/10 text-foreground'
                : 'border-input text-muted-foreground hover:text-foreground hover:bg-muted',
            )}
          >
            {toggle.label}
          </button>
        )
      })}

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
