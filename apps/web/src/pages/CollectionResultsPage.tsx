import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import { COLLECTION_ICONS } from '@/components/collections/icons'
import { MovieGrid } from '@/components/movies/MovieGrid'
import { describeFilters, fetchSmartCollectionResults } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'

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
      <PageHeader
        backTo="/collections"
        backLabel="All collections"
        eyebrow={<span className="inline-flex items-center gap-2">{Icon ? <Icon className="h-4 w-4" aria-hidden /> : null}Saved collection</span>}
        title={collection?.name ?? 'Collection'}
        description={collection ? describeFilters(collection.filters) : 'Loading this saved collection…'}
        meta={collection ? <span>{resultsQuery.data?.totalMovies.toLocaleString() ?? '0'} films</span> : undefined}
        className="mb-0 px-4 py-4 sm:px-6 lg:px-8"
      />

      {state === 'offline' ? (
        <StatePanel tone="offline" title="This collection is not cached here" description="Reconnect to evaluate its filters against the archive." className="m-4 flex-1" />
      ) : state === 'error' ? (
        <StatePanel tone="error" title="This collection could not be opened" description={queryErrorMessage(resultsQuery.error, 'The server did not answer.')} className="m-4 flex-1" />
      ) : state === 'empty' ? (
        <StatePanel tone="empty" title="Nothing matches yet" description="This collection will update automatically when a matching disc is added." className="m-4 flex-1" />
      ) : (
        <MovieGrid movies={movies} isLoading={state === 'loading'} />
      )}
    </div>
  )
}
