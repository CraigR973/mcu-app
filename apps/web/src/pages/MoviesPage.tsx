import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { fetchMovies, type MovieFilters } from '@/lib/api'
import { FilterBar } from '@/components/movies/FilterBar'
import { MovieGrid } from '@/components/movies/MovieGrid'
import { MovieListView } from '@/components/movies/MovieListView'
import { MovieCompactView } from '@/components/movies/MovieCompactView'
import { ViewToggle } from '@/components/movies/ViewToggle'
import { useViewPreference } from '@/hooks/useViewPreference'
import AddToCollectionDialog from '@/components/AddToCollectionDialog'
import { useAuth } from '@/context/auth'

export default function MoviesPage() {
  const [filters, setFilters] = useState<MovieFilters>({})
  const { viewMode, setViewMode, enabledColumns, toggleColumn } = useViewPreference()
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'

  const { data, isLoading, isError } = useQuery({
    queryKey: ['movies', filters],
    queryFn: () => fetchMovies({ ...filters, per_page: 2000 }),
    staleTime: 5 * 60 * 1000,
  })

  const movies = data?.data ?? []
  const total = data?.meta.total ?? 0

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-4 px-4 py-3 border-b border-border">
        <h1 className="text-lg font-semibold text-foreground shrink-0">Movies</h1>
        <div className="ml-auto flex items-center gap-2">
          {isAdmin && (
            <button
              type="button"
              onClick={() => setAddDialogOpen(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <Plus className="h-4 w-4" />
              Add Movie
            </button>
          )}
          <ViewToggle value={viewMode} onChange={setViewMode} />
        </div>
      </div>

      <AddToCollectionDialog open={addDialogOpen} onClose={() => setAddDialogOpen(false)} />

      <FilterBar
        filters={filters}
        total={isLoading ? 0 : total}
        onChange={setFilters}
      />

      {isError && (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-destructive">Failed to load movies. Please refresh.</p>
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
