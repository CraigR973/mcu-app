import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchMovies, type MovieFilters } from '@/lib/api'
import { FilterBar } from '@/components/movies/FilterBar'
import { MovieGrid } from '@/components/movies/MovieGrid'

export default function MoviesPage() {
  const [filters, setFilters] = useState<MovieFilters>({})

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
      </div>

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

      {!isError && (
        <MovieGrid movies={movies} isLoading={isLoading} />
      )}
    </div>
  )
}
