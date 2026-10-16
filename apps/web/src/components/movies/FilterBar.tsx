import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowUpDown, ChevronDown, SlidersHorizontal, X } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  fetchFacets,
  FORMATS,
  MIN_RATING_OPTIONS,
  runtimeLabel,
  shelfLabel,
  TMDB_GENRES,
  type MovieFilters,
} from '@/lib/api'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/utils'

interface Props {
  filters: MovieFilters
  total?: number
  onChange: (filters: MovieFilters) => void
  context?: 'browse' | 'saved'
  /** Batch T3, snag 1: the layout switch, drawn at the end of the same row. */
  trailing?: ReactNode
}

const SORT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'title:asc', label: 'Title A–Z' },
  { value: 'title:desc', label: 'Title Z–A' },
  { value: 'year:desc', label: 'Newest first' },
  { value: 'year:asc', label: 'Oldest first' },
  { value: 'rating:desc', label: 'Highest rated' },
]

function parseMinutes(value: string): number | undefined {
  const minutes = Number.parseInt(value, 10)
  return Number.isFinite(minutes) && minutes > 0 ? minutes : undefined
}

/**
 * Batch T3, snag 2 — runtime from and to, in minutes.
 *
 * Typed values are held here and applied after a pause, because every change refetches
 * the whole catalogue: "120" should be one request, not three. A range whose "from" is
 * longer than its "to" is never applied; the API would refuse it.
 */
function RuntimeRange({ filters, onChange }: { filters: MovieFilters; onChange: (filters: MovieFilters) => void }) {
  const [from, setFrom] = useState(filters.runtimeMin != null ? String(filters.runtimeMin) : '')
  const [to, setTo] = useState(filters.runtimeMax != null ? String(filters.runtimeMax) : '')

  useEffect(() => {
    setFrom(filters.runtimeMin != null ? String(filters.runtimeMin) : '')
    setTo(filters.runtimeMax != null ? String(filters.runtimeMax) : '')
  }, [filters.runtimeMin, filters.runtimeMax])

  const min = parseMinutes(from)
  const max = parseMinutes(to)
  const backwards = min != null && max != null && min > max

  useEffect(() => {
    if (backwards || (min === filters.runtimeMin && max === filters.runtimeMax)) return
    const timer = setTimeout(() => onChange({ ...filters, runtimeMin: min, runtimeMax: max }), 500)
    return () => clearTimeout(timer)
  }, [backwards, filters, max, min, onChange])

  return (
    <fieldset className="min-w-0">
      <legend className="field-label">Runtime, in minutes</legend>
      <div className="mt-1 flex items-center gap-2">
        <input
          type="number"
          min="1"
          max="1000"
          inputMode="numeric"
          className="form-control w-24"
          value={from}
          onChange={(event) => setFrom(event.target.value)}
          placeholder="From"
          aria-label="Shortest runtime in minutes"
        />
        <span aria-hidden className="text-muted-foreground">–</span>
        <input
          type="number"
          min="1"
          max="1000"
          inputMode="numeric"
          className="form-control w-24"
          value={to}
          onChange={(event) => setTo(event.target.value)}
          placeholder="To"
          aria-label="Longest runtime in minutes"
        />
      </div>
      {backwards ? (
        <p role="alert" className="mt-1 text-xs text-destructive">The shortest can't be longer than the longest.</p>
      ) : null}
    </fieldset>
  )
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

/**
 * **Batch T3, snag 1: one row at every width** — Filters, Sort, the film count once, and
 * whatever the page puts at the end (the Archive's layout switch). Below 1280px, location
 * and format live in the Filters panel; above it they join the row.
 *
 * Batch S3, snag 5: **below `sm` this is a single button.**
 *
 * It used to put four controls — section, format, a Filters toggle and a sort — across a
 * 375px screen, above every page of the Archive. Wrapped onto three rows, they cost more
 * vertical space than the first film poster.
 *
 * `useMediaQuery` decides *where* the three selects render rather than rendering them
 * twice and hiding one with CSS: two copies of a `<select>` labelled "Filter by section"
 * is a duplicate id and a duplicate accessible name, and the hidden one comes back the
 * moment somebody changes a `hidden` class. One copy, one place, chosen at runtime.
 */
export function FilterBar({ filters, total, onChange, context = 'browse', trailing }: Props) {
  const isNarrow = !useMediaQuery('(min-width: 640px)')
  const isWide = useMediaQuery('(min-width: 1280px)')
  const location = useLocation()
  const navigate = useNavigate()
  const supportsLiveOnly = context === 'browse'

  // Mark, 15 Oct: on a phone the open panel fills the screen, and the virtualised grid below
  // it shrinks to nothing, so a filter's films could not be reached; swiping back left the
  // app. Below 1280px the Archive's open panel is a history entry, so back closes it, and it
  // ends in a "Show films" button. Elsewhere, and in a saved collection's editor, it is
  // plain state.
  const historyBacked = supportsLiveOnly && !isWide
  const [openHere, setOpenHere] = useState(false)
  const openInHistory = (location.state as { filtersOpen?: unknown } | null)?.filtersOpen === true
  const expanded = historyBacked ? openInHistory : openHere
  const setExpanded = (open: boolean) => {
    if (!historyBacked) {
      setOpenHere(open)
    } else if (open && !openInHistory) {
      const state = (location.state as Record<string, unknown> | null) ?? {}
      navigate(
        { pathname: location.pathname, search: location.search, hash: location.hash },
        { state: { ...state, filtersOpen: true } },
      )
    } else if (!open && openInHistory) {
      // The entry was pushed by opening the panel, so the one behind it is this page, closed.
      navigate(-1)
    }
  }
  const facetsQuery = useQuery({
    queryKey: ['collection-facets'],
    queryFn: fetchFacets,
    staleTime: 30 * 60 * 1000,
  })

  const sections = facetsQuery.data?.sections ?? []
  const decades = facetsQuery.data?.decades ?? []
  const selectedSection = sections.find((section) => section.section === filters.section)
  const shelves = selectedSection?.shelves ?? []
  // The Lounge's subdivisions are sides, not shelves (Mark, 14 Oct).
  const sides = selectedSection?.shelfNoun === 'side'
  // Batch T7, #154's rule: the spec filters hide until a disc has specs to match them.
  const specsAvailable = (facetsQuery.data?.discsWithSpecs ?? 0) > 0
  // Mark's request, 14 Oct: the Archive lists the films still to identify, and each one's
  // page has the identify panel. Hidden at 0, by #154's rule, and in a saved collection.
  const toIdentifyCount = facetsQuery.data?.toIdentifyMovieCount ?? 0
  // Batch Y4: and the identified films in doubt, which either person settles from the page.
  const inDoubtCount = facetsQuery.data?.inDoubtMovieCount ?? 0
  const identifyChoice = filters.toIdentify ? 'true' : filters.inDoubt ? 'in-doubt' : ''

  const activeFilters = useMemo(() => {
    const active: Array<{ key: string; label: string; clear: () => void }> = []
    const add = (key: string, label: string, patch: Partial<MovieFilters>) =>
      active.push({ key, label, clear: () => onChange({ ...filters, ...patch }) })

    if (filters.section) add('section', `Section: ${filters.section}`, { section: undefined, shelf: undefined })
    if (filters.shelf) {
      const picked = selectedSection?.shelves.find((entry) => entry.shelf === filters.shelf)
      add('shelf', picked && sides ? `Side: ${shelfLabel(picked)}` : `Shelf: ${filters.shelf}`, { shelf: undefined })
    }
    if (filters.format) add('format', FORMATS.find((format) => format.value === filters.format)?.label ?? filters.format, { format: undefined })
    if (filters.genreId) add('genre', TMDB_GENRES.find((genre) => genre.id === filters.genreId)?.name ?? 'Genre', { genreId: undefined })
    if (filters.year) add('year', `Year: ${filters.year}`, { year: undefined })
    if (filters.decadeFrom) add('decade-from', `From ${filters.decadeFrom}s`, { decadeFrom: undefined })
    if (filters.decadeTo) add('decade-to', `Through ${filters.decadeTo}s`, { decadeTo: undefined })
    if (filters.minRating != null) add('rating', `Rated ${filters.minRating}+`, { minRating: undefined })
    const runtime = runtimeLabel(filters.runtimeMin, filters.runtimeMax)
    if (runtime) add('runtime', runtime.charAt(0).toUpperCase() + runtime.slice(1), { runtimeMin: undefined, runtimeMax: undefined })
    if (filters.watched != null) add('watched', filters.watched ? 'Watched' : 'Not watched', { watched: undefined })
    if (filters.toIdentify) add('to-identify', 'Still to identify', { toIdentify: undefined })
    if (filters.inDoubt) add('in-doubt', 'In doubt', { inDoubt: undefined })
    if (filters.hdr) add('hdr', filters.hdr, { hdr: undefined })
    if (filters.audio) add('audio', filters.audio, { audio: undefined })
    if (filters.regionFree) add('region', 'Region-free', { regionFree: undefined })
    return active
  }, [filters, onChange, selectedSection, sides])

  // In the wide row, location and format are on show beside the button; everywhere else
  // they are inside it, and so is everything it counts.
  const advancedCount = isWide
    ? activeFilters.filter(({ key }) => !['section', 'shelf', 'format'].includes(key)).length
    : activeFilters.length

  const sectionSelect = (
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
  )

  const formatSelect = (
    <select
      className={CONTROL_CLS}
      value={filters.format ?? ''}
      onChange={(event) => onChange({ ...filters, format: event.target.value || undefined })}
      aria-label="Filter by format"
    >
      <option value="">All formats</option>
      {FORMATS.map((format) => <option key={format.value} value={format.value}>{format.label}</option>)}
    </select>
  )

  const sortValue = `${filters.sort ?? 'title'}:${filters.order ?? 'asc'}`
  const sortLabel = SORT_OPTIONS.find((option) => option.value === sortValue)?.label ?? 'Title A–Z'
  const onSort = (value: string) => {
    const [sort, order] = value.split(':') as [NonNullable<MovieFilters['sort']>, NonNullable<MovieFilters['order']>]
    onChange({ ...filters, sort, order })
  }
  const sortOptions = SORT_OPTIONS.map((option) => (
    <option key={option.value} value={option.value}>{option.label}</option>
  ))

  // Batch T3: on a phone the sort is an icon that opens the full list. Every control here
  // is 44px wide on a touch screen, and a labelled box could not share one 375px row with
  // Filters, the count and three layout buttons.
  const sortSelect = !supportsLiveOnly ? null : isNarrow ? (
    <label className="touch-target relative inline-flex shrink-0 items-center justify-center rounded-md border border-input bg-card text-muted-foreground">
      <ArrowUpDown className="h-4 w-4" aria-hidden />
      <select
        id="collection-sort"
        aria-label={`Sort collection, now ${sortLabel}`}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        value={sortValue}
        onChange={(event) => onSort(event.target.value)}
      >
        {sortOptions}
      </select>
    </label>
  ) : (
    <>
      <label htmlFor="collection-sort" className="sr-only">Sort collection</label>
      <select
        id="collection-sort"
        className={cn(CONTROL_CLS, 'w-auto shrink-0 xl:min-w-40')}
        value={sortValue}
        onChange={(event) => onSort(event.target.value)}
      >
        {sortOptions}
      </select>
    </>
  )

  const filtersToggle = (
    <Button
      type="button"
      variant="outline"
      className="shrink-0 justify-between gap-2 px-3"
      aria-expanded={expanded}
      aria-controls="collection-more-filters"
      onClick={() => setExpanded(!expanded)}
    >
      <span className="inline-flex items-center gap-2">
        <SlidersHorizontal className="h-4 w-4" aria-hidden /> Filters
        {advancedCount > 0 && <Badge tone="primary" className="min-w-5 justify-center px-1">{advancedCount}</Badge>}
      </span>
      <ChevronDown className={cn('hidden h-4 w-4 transition-transform sm:block', expanded && 'rotate-180')} aria-hidden />
    </Button>
  )

  // The count is a reading, not a control: the answer to "did that filter do anything".
  // Batch T3: it appears here and nowhere else, and on a phone as the bare number.
  const filmCount =
    total != null ? (
      <span aria-live="polite" className="whitespace-nowrap text-xs tabular-nums text-muted-foreground">
        {total.toLocaleString()}
        <span className={cn(isNarrow && 'sr-only')}> {total === 1 ? 'film' : 'films'}</span>
      </span>
    ) : null

  return (
    <section aria-label="Collection filters" className="border-b border-border bg-surface-sunken/35">
      <div className="px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-1.5 sm:gap-2" data-testid="collection-controls-row">
          {isWide && (
            <>
              <div className="w-44 shrink-0">{sectionSelect}</div>
              <div className="w-40 shrink-0">{formatSelect}</div>
            </>
          )}
          {filtersToggle}
          {sortSelect}
          <span className="ml-auto" />
          {filmCount}
          {trailing}
        </div>

        {facetsQuery.isError && (
          <p role="alert" className="mt-2 text-xs text-destructive">Location and decade choices are temporarily unavailable. Existing filters still apply.</p>
        )}

        {expanded && (
          <div id="collection-more-filters" className="mt-3 border-t border-border pt-3">
            {/* Below 1280px, location and format live here rather than in the row, so
                collapsing the panel hides them rather than removing them. */}
            {!isWide && (
              <div className="mb-2 grid gap-2 sm:grid-cols-2">
                {sectionSelect}
                {formatSelect}
              </div>
            )}
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
              {shelves.length > 0 && (
                <select className={CONTROL_CLS} value={filters.shelf ?? ''} onChange={(event) => onChange({ ...filters, shelf: event.target.value || undefined })} aria-label={sides ? 'Filter by side' : 'Filter by shelf'}>
                  <option value="">{sides ? 'Both sides' : 'All shelves'}</option>
                  {shelves.map((shelf) => <option key={shelf.shelf} value={shelf.shelf}>{shelfLabel(shelf)} ({shelf.itemCount})</option>)}
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
              {supportsLiveOnly && (toIdentifyCount > 0 || inDoubtCount > 0 || filters.toIdentify || filters.inDoubt) && (
                <select className={CONTROL_CLS} value={identifyChoice} onChange={(event) => onChange({ ...filters, toIdentify: event.target.value === 'true' || undefined, inDoubt: event.target.value === 'in-doubt' || undefined })} aria-label="Filter by identified or not">
                  <option value="">Identified or not</option>
                  {(toIdentifyCount > 0 || filters.toIdentify) && <option value="true">Still to identify ({toIdentifyCount})</option>}
                  {(inDoubtCount > 0 || filters.inDoubt) && <option value="in-doubt">In doubt ({inDoubtCount})</option>}
                </select>
              )}
            </div>

            <div className="mt-3">
              <RuntimeRange filters={filters} onChange={onChange} />
            </div>

            {supportsLiveOnly && specsAvailable && (
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

            {historyBacked && (
              <Button type="button" className="mt-4 w-full sm:w-auto" onClick={() => setExpanded(false)}>
                {total != null ? `Show ${total.toLocaleString()} ${total === 1 ? 'film' : 'films'}` : 'Show films'}
              </Button>
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
