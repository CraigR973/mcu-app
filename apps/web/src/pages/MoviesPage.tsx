import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMovies, type MovieFilters } from '@/lib/api'
import { FilterBar } from '@/components/movies/FilterBar'
import { MovieGrid } from '@/components/movies/MovieGrid'
import { MovieListView } from '@/components/movies/MovieListView'
import { MovieCompactView } from '@/components/movies/MovieCompactView'
import { ViewToggle } from '@/components/movies/ViewToggle'
import { useViewPreference } from '@/hooks/useViewPreference'

export default function MoviesPage() {
  const [filters, setFilters] = useState<MovieFilters>({})
  const { viewMode, setViewMode, enabledColumns, toggleColumn } = useViewPreference()

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['movies', filters],
    // The three collection views are virtualised. Loading the catalogue in one page
    // gives them the full scroll range while keeping only the visible rows in the DOM.
    queryFn: () => fetchMovies(filters, 1, 2000),
    staleTime: 5 * 60 * 1000,
  })

  const movies = data?.items ?? []
  const totalMovies = data?.totalMovies ?? 0
  const totalItems = data?.totalItems ?? 0

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-4 px-4 py-3 border-b border-border">
        <h1 className="text-lg font-semibold text-foreground shrink-0">Movies</h1>
        <p className="hidden text-xs text-muted-foreground sm:block">
          {totalMovies.toLocaleString()} films · {totalItems.toLocaleString()} items
        </p>
        <div className="ml-auto flex items-center gap-2">
          <ViewToggle value={viewMode} onChange={setViewMode} />
        </div>
      </div>

      <FilterBar
        filters={filters}
        total={isLoading ? 0 : totalMovies}
        onChange={setFilters}
      />

      {isError && (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-destructive">
            {error instanceof Error ? error.message : 'Failed to load movies. Please refresh.'}
          </p>
        </div>
      )}

      {!isError && viewMode === 'grid' && (
        <MovieGrid movies={movies} isLoading={isLoading} />
      )}

      {!isError && viewMode === 'list' && (
        <MovieListView
          movies={movies}
          isLoading={isLoading}
          enabledColumns={enabledColumns}
          toggleColumn={toggleColumn}
        />
      )}

      {!isError && viewMode === 'compact' && (
        <MovieCompactView movies={movies} isLoading={isLoading} />
      )}
    </div>
  )
}
