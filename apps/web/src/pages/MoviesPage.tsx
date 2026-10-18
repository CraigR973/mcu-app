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

/** How many films the first answer carries: enough to fill a phone screen and the scroll
 *  beyond it, small enough to arrive in a fraction of the full list's time (Batch X12b,
 *  UX48-07: the Archive showed nothing until all 1,891 films had arrived, 2.0 s on 4G and
 *  7.8 s on a weak link). */
const FIRST_SCREEN = 60

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

  // The first screen is asked for on its own, so films show while the rest is still on its
  // way; the three views are virtualised, so the full list then replaces it without a jump.
  const firstScreen = useQuery({
    queryKey: ['movies', filters, 'first-screen'],
    queryFn: () => fetchMovies(filters, 1, FIRST_SCREEN),
    staleTime: 5 * 60 * 1000,
  })
  const moviesQuery = useQuery({
    queryKey: ['movies', filters],
    // The three collection views are virtualised. Loading the catalogue in one page
    // gives them the full scroll range while keeping only the visible rows in the DOM.
    queryFn: () => fetchMovies(filters, 1, 2000),
    staleTime: 5 * 60 * 1000,
  })
  // What is on screen: the whole list once it is here, else the first screen if that is.
  const view = moviesQuery.data ? moviesQuery : firstScreen.data ? firstScreen : moviesQuery
  const restPending = !moviesQuery.data && Boolean(firstScreen.data)

  useEffect(() => {
    try {
      sessionStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(filters))
    } catch {
      // Browsing still works when storage is unavailable.
    }
  }, [filters])

  const movies = view.data?.items ?? []
  const totalMovies = view.data?.totalMovies ?? 0
  const state = listState(view, movies.length === 0)

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

      {restPending && state === 'ready' && movies.length < totalMovies ? (
        <p role="status" className="px-4 py-1 text-xs text-muted-foreground">
          {moviesQuery.isError
            ? `Showing the first ${String(movies.length)} of ${String(totalMovies)} films; the rest could not be loaded.`
            : `Showing the first ${String(movies.length)} of ${String(totalMovies)} films; loading the rest…`}
          {moviesQuery.isError ? (
            <Button variant="ghost" size="sm" className="ml-2" onClick={() => void moviesQuery.refetch()}>
              Try again
            </Button>
          ) : null}
        </p>
      ) : null}

      {state === 'offline' && (
        <StatePanel tone="offline" title="The archive has not been cached here yet" description="Reconnect once to load this collection on this device." className="m-4 flex-1" />
      )}

      {state === 'error' && (
        <StatePanel
          tone="error"
          title="The archive could not be opened"
          description={queryErrorMessage(view.error, 'The server did not answer. Your filters have been kept.')}
          action={<Button variant="outline" onClick={() => void view.refetch()}>Try again</Button>}
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
