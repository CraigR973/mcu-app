import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMovies, type MovieFilters } from '@/lib/api'
import { FilterBar } from '@/components/movies/FilterBar'
import { MovieGrid } from '@/components/movies/MovieGrid'
import { MovieListView } from '@/components/movies/MovieListView'
import { MovieCompactView } from '@/components/movies/MovieCompactView'
import { ViewToggle } from '@/components/movies/ViewToggle'
import { useViewPreference } from '@/hooks/useViewPreference'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { Button } from '@/components/ui/button'
import { listState, queryErrorMessage } from '@/lib/query-state'

const FILTER_STORAGE_KEY = 'mcu-collection-filters'

function restoredFilters(): MovieFilters {
  try {
    const value: unknown = JSON.parse(sessionStorage.getItem(FILTER_STORAGE_KEY) ?? '{}')
    return value && typeof value === 'object' && !Array.isArray(value) ? value as MovieFilters : {}
  } catch {
    return {}
  }
}

export default function MoviesPage() {
  const [filters, setFilters] = useState<MovieFilters>(restoredFilters)
  const { viewMode, setViewMode, enabledColumns, toggleColumn } = useViewPreference()

  const moviesQuery = useQuery({
    queryKey: ['movies', filters],
    // The three collection views are virtualised. Loading the catalogue in one page
    // gives them the full scroll range while keeping only the visible rows in the DOM.
    queryFn: () => fetchMovies(filters, 1, 2000),
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    try {
      sessionStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(filters))
    } catch {
      // Browsing still works when storage is unavailable.
    }
  }, [filters])

  const movies = moviesQuery.data?.items ?? []
  const totalMovies = moviesQuery.data?.totalMovies ?? 0
  const state = listState(moviesQuery, movies.length === 0)

  return (
    <div className="flex flex-col h-full">
      {/* Batch T3, snag 1. The title is all the header keeps, and only on a desktop — on a
          phone it lives in the top bar. The count and the layout switch moved into the
          filter row, so the count is said once and the controls take one line. */}
      <PageHeader
        eyebrow="Collection catalogue"
        title="The archive"
        className="mb-0 px-4 py-4 sm:items-center sm:px-6 sm:py-5 lg:px-8"
      />

      <FilterBar
        filters={filters}
        total={state === 'loading' ? undefined : totalMovies}
        onChange={setFilters}
        trailing={<ViewToggle value={viewMode} onChange={setViewMode} />}
      />

      {state === 'offline' && (
        <StatePanel tone="offline" title="The archive has not been cached here yet" description="Reconnect once to load this collection on this device." className="m-4 flex-1" />
      )}

      {state === 'error' && (
        <StatePanel
          tone="error"
          title="The archive could not be opened"
          description={queryErrorMessage(moviesQuery.error, 'The server did not answer. Your filters have been kept.')}
          action={<Button variant="outline" onClick={() => void moviesQuery.refetch()}>Try again</Button>}
          className="m-4 flex-1"
        />
      )}

      {state !== 'error' && state !== 'offline' && viewMode === 'grid' && (
        <MovieGrid movies={movies} isLoading={state === 'loading'} />
      )}

      {state !== 'error' && state !== 'offline' && viewMode === 'list' && (
        <MovieListView
          movies={movies}
          isLoading={state === 'loading'}
          enabledColumns={enabledColumns}
          toggleColumn={toggleColumn}
        />
      )}

      {state !== 'error' && state !== 'offline' && viewMode === 'compact' && (
        <MovieCompactView movies={movies} isLoading={state === 'loading'} />
      )}
    </div>
  )
}
