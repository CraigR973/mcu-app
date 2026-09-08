import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { COLLECTION_ICONS } from '@/components/collections/icons'
import { MovieGrid } from '@/components/movies/MovieGrid'
import { describeFilters, fetchSmartCollectionResults } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

/**
 * One saved collection's current results — §11.5's "lists correct films and updates
 * live".
 *
 * The films are rendered by `MovieGrid`, the same component the collection view uses.
 * A second card that showed the same film differently would make the two views
 * disagree about what a film looks like, and the API already guarantees they agree
 * about which films there are.
 */
export default function CollectionResultsPage() {
  const { id = '' } = useParams<{ id: string }>()

  const resultsQuery = useQuery({
    queryKey: ['smart-collection-results', id],
    queryFn: () => fetchSmartCollectionResults(id),
    // No `staleTime`: "updates live" is this page's entire promise, and a cached page
    // that outlives a newly added disc is the one way to break it.
    staleTime: 0,
  })

  const collection = resultsQuery.data?.collection
  const movies = resultsQuery.data?.items ?? []
  const state = listState(resultsQuery, movies.length === 0)
  const Icon = collection ? COLLECTION_ICONS[collection.icon] : null

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <Link
          to="/collections"
          className="text-muted-foreground hover:text-foreground"
          aria-label="Back to collections"
        >
          <ArrowLeft className="h-4 w-4" />
        </Link>
        {Icon ? <Icon className="h-5 w-5 text-primary" /> : null}
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold text-foreground">
            {collection?.name ?? 'Collection'}
          </h1>
          {collection ? (
            <p className="truncate text-xs text-muted-foreground">
              {describeFilters(collection.filters)} ·{' '}
              {resultsQuery.data?.totalMovies.toLocaleString() ?? '0'} films
            </p>
          ) : null}
        </div>
      </div>

      {state === 'offline' ? (
        <p className="p-4 text-sm text-muted-foreground">
          Waiting for the network — these results could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="p-4 text-sm text-destructive">
          {queryErrorMessage(resultsQuery.error, 'Could not load this collection.')}
        </p>
      ) : state === 'empty' ? (
        <p className="p-8 text-center text-sm text-muted-foreground">
          Nothing in the collection matches these filters yet.
        </p>
      ) : (
        <MovieGrid movies={movies} isLoading={state === 'loading'} />
      )}
    </div>
  )
}
