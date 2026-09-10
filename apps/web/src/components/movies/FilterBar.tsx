import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, SlidersHorizontal, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
  total?: number
  onChange: (filters: MovieFilters) => void
  context?: 'browse' | 'saved'
}

const CONTROL_CLS = 'select-control min-w-0 text-sm'

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

export function FilterBar({ filters, total, onChange, context = 'browse' }: Props) {
  const [expanded, setExpanded] = useState(false)
  const facetsQuery = useQuery({
    queryKey: ['collection-facets'],
    queryFn: fetchFacets,
    staleTime: 30 * 60 * 1000,
  })

  const sections = facetsQuery.data?.sections ?? []
  const decades = facetsQuery.data?.decades ?? []
  const selectedSection = sections.find((section) => section.section === filters.section)
  const shelves = selectedSection?.shelves ?? []
  const supportsLiveOnly = context === 'browse'

  const activeFilters = useMemo(() => {
    const active: Array<{ key: string; label: string; clear: () => void }> = []
    const add = (key: string, label: string, patch: Partial<MovieFilters>) =>
      active.push({ key, label, clear: () => onChange({ ...filters, ...patch }) })

    if (filters.section) add('section', `Section: ${filters.section}`, { section: undefined, shelf: undefined })
    if (filters.shelf) add('shelf', `Shelf: ${filters.shelf}`, { shelf: undefined })
    if (filters.format) add('format', FORMATS.find((format) => format.value === filters.format)?.label ?? filters.format, { format: undefined })
    if (filters.genreId) add('genre', TMDB_GENRES.find((genre) => genre.id === filters.genreId)?.name ?? 'Genre', { genreId: undefined })
    if (filters.year) add('year', `Year: ${filters.year}`, { year: undefined })
    if (filters.decadeFrom) add('decade-from', `From ${filters.decadeFrom}s`, { decadeFrom: undefined })
    if (filters.decadeTo) add('decade-to', `Through ${filters.decadeTo}s`, { decadeTo: undefined })
    if (filters.minRating != null) add('rating', `Rated ${filters.minRating}+`, { minRating: undefined })
    if (filters.watched != null) add('watched', filters.watched ? 'Watched' : 'Not watched', { watched: undefined })
    if (filters.hdr) add('hdr', filters.hdr, { hdr: undefined })
    if (filters.audio) add('audio', filters.audio, { audio: undefined })
    if (filters.regionFree) add('region', 'Region-free', { regionFree: undefined })
    return active
  }, [filters, onChange])

  const advancedCount = activeFilters.filter(({ key }) => !['section', 'shelf', 'format'].includes(key)).length

  return (
    <section aria-label="Collection filters" className="border-b border-border bg-surface-sunken/35">
      <div className="px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-2 xl:flex-row xl:items-center">
          <div className="grid min-w-0 flex-1 grid-cols-2 gap-2 md:grid-cols-[minmax(10rem,1fr)_minmax(9rem,0.8fr)_auto] xl:max-w-3xl">
            <select
              className={CONTROL_CLS}
              value={filters.section ?? ''}
              onChange={(event) => onChange({ ...filters, section: event.target.value || undefined, shelf: undefined })}
              aria-label="Filter by section"
            >
              <option value="">All locations</option>
              {sections.map((section) => (
                <option key={section.section} value={section.section}>{section.section} ({section.itemCount})</option>
              ))}
            </select>

            <select
              className={CONTROL_CLS}
              value={filters.format ?? ''}
              onChange={(event) => onChange({ ...filters, format: event.target.value || undefined })}
              aria-label="Filter by format"
            >
              <option value="">All formats</option>
              {FORMATS.map((format) => <option key={format.value} value={format.value}>{format.label}</option>)}
            </select>

            <Button
              type="button"
              variant="outline"
              className="col-span-2 justify-between md:col-span-1"
              aria-expanded={expanded}
              aria-controls="collection-more-filters"
              onClick={() => setExpanded((value) => !value)}
            >
              <span className="inline-flex items-center gap-2">
                <SlidersHorizontal className="h-4 w-4" aria-hidden /> Filters
                {advancedCount > 0 && <Badge tone="primary" className="min-w-5 justify-center px-1">{advancedCount}</Badge>}
              </span>
              <ChevronDown className={cn('h-4 w-4 transition-transform', expanded && 'rotate-180')} aria-hidden />
            </Button>
          </div>

          {supportsLiveOnly && (
            <div className="flex items-center gap-2 xl:ml-auto">
              <label htmlFor="collection-sort" className="sr-only">Sort collection</label>
              <select
                id="collection-sort"
                className={cn(CONTROL_CLS, 'flex-1 xl:min-w-40')}
                value={`${filters.sort ?? 'title'}:${filters.order ?? 'asc'}`}
                onChange={(event) => {
                  const [sort, order] = event.target.value.split(':') as [NonNullable<MovieFilters['sort']>, NonNullable<MovieFilters['order']>]
                  onChange({ ...filters, sort, order })
                }}
              >
                <option value="title:asc">Title A–Z</option>
                <option value="title:desc">Title Z–A</option>
                <option value="year:desc">Newest first</option>
                <option value="year:asc">Oldest first</option>
                <option value="rating:desc">Highest rated</option>
              </select>
              {total != null && (
                <span aria-live="polite" className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
                  {total.toLocaleString()} {total === 1 ? 'film' : 'films'}
                </span>
              )}
            </div>
          )}
        </div>

        {facetsQuery.isError && (
          <p role="alert" className="mt-2 text-xs text-destructive">Location and decade choices are temporarily unavailable. Existing filters still apply.</p>
        )}

        {expanded && (
          <div id="collection-more-filters" className="mt-3 border-t border-border pt-3">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
              {shelves.length > 0 && (
                <select className={CONTROL_CLS} value={filters.shelf ?? ''} onChange={(event) => onChange({ ...filters, shelf: event.target.value || undefined })} aria-label="Filter by shelf">
                  <option value="">All shelves</option>
                  {shelves.map((shelf) => <option key={shelf.shelf} value={shelf.shelf}>{shelf.shelf} shelf ({shelf.itemCount})</option>)}
                </select>
              )}
              <select className={CONTROL_CLS} value={filters.genreId ?? ''} onChange={(event) => onChange({ ...filters, genreId: event.target.value ? Number(event.target.value) : undefined })} aria-label="Filter by genre">
                <option value="">All genres</option>
                {TMDB_GENRES.map((genre) => <option key={genre.id} value={genre.id}>{genre.name}</option>)}
              </select>
              <input
                type="number"
                min="1870"
                max="2100"
                inputMode="numeric"
                className="form-control"
                value={filters.year ?? ''}
                onChange={(event) => onChange({ ...filters, year: event.target.value ? Number(event.target.value) : undefined })}
                placeholder="Exact year"
                aria-label="Filter by exact year"
              />
              <select className={CONTROL_CLS} value={filters.decadeFrom ?? ''} onChange={(event) => onChange({ ...filters, decadeFrom: event.target.value ? Number(event.target.value) : undefined })} aria-label="Earliest decade">
                <option value="">Any start decade</option>
                {decades.map((decade) => <option key={decade.decade} value={decade.decade}>{decade.decade}s ({decade.movieCount})</option>)}
              </select>
              <select className={CONTROL_CLS} value={filters.decadeTo ?? ''} onChange={(event) => onChange({ ...filters, decadeTo: event.target.value ? Number(event.target.value) : undefined })} aria-label="Latest decade">
                <option value="">Through today</option>
                {decades.map((decade) => <option key={decade.decade} value={decade.decade}>{decade.decade}s</option>)}
              </select>
              <select className={CONTROL_CLS} value={filters.minRating ?? ''} onChange={(event) => onChange({ ...filters, minRating: event.target.value ? Number(event.target.value) : undefined })} aria-label="Minimum TMDB rating">
                <option value="">Any rating</option>
                {MIN_RATING_OPTIONS.map((rating) => <option key={rating} value={rating}>{rating}+ rating</option>)}
              </select>
              <select className={CONTROL_CLS} value={filters.watched === undefined ? '' : String(filters.watched)} onChange={(event) => onChange({ ...filters, watched: event.target.value === '' ? undefined : event.target.value === 'true' })} aria-label="Filter by watched status">
                <option value="">Watched or not</option>
                <option value="true">Watched</option>
                <option value="false">Not watched</option>
              </select>
            </div>

            {supportsLiveOnly && (
              <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Technical specification filters">
                {SPEC_TOGGLES.map((toggle) => {
                  const active = toggle.isActive(filters)
                  return (
                    <Button key={toggle.label} type="button" size="sm" variant={active ? 'secondary' : 'outline'} aria-pressed={active} onClick={() => onChange({ ...filters, ...toggle.apply(active) })}>
                      {toggle.label}
                    </Button>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {activeFilters.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3" aria-label="Active filters">
            <span className="text-xs font-semibold text-muted-foreground">Showing</span>
            {activeFilters.map((filter) => (
              <button key={filter.key} type="button" onClick={filter.clear} className="touch-target inline-flex min-h-8 items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 text-xs font-semibold text-foreground hover:bg-primary/15" aria-label={`Remove ${filter.label} filter`}>
                {filter.label}<X className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              </button>
            ))}
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange({})}>Clear all</Button>
          </div>
        )}
      </div>
    </section>
  )
}
