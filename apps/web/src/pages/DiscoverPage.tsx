import { useQuery } from '@tanstack/react-query'
import { Check, Sparkle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { fetchNewReleases, posterUrl } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/**
 * §7.2's "new releases feed filtered by collected genres".
 *
 * The genres come from the collection itself, not a settings screen, so the feed is right
 * on day one and stays right as the shelves change. Each card says which genre put it
 * there — a suggestion that cannot explain itself is indistinguishable from a random one.
 */
export default function DiscoverPage() {
  const releasesQuery = useQuery({
    queryKey: ['new-releases'],
    queryFn: fetchNewReleases,
    staleTime: 60 * 60 * 1000,
  })
  const items = releasesQuery.data?.items ?? []
  const state = listState(releasesQuery, items.length === 0)

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Coming soon</h1>
        <p className="text-sm text-muted-foreground">
          New releases in the genres this collection actually leans on
          {releasesQuery.data && releasesQuery.data.basedOnGenres.length > 0
            ? `: ${releasesQuery.data.basedOnGenres.join(', ')}.`
            : '.'}
        </p>
      </div>

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — new releases could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(releasesQuery.error, 'Could not load new releases.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Sparkle className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            Nothing upcoming matches this collection&rsquo;s genres right now.
          </p>
        </div>
      ) : (
        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
          {items.map((item) => {
            const card = (
              <div className="space-y-1">
                <div className="relative">
                  <img
                    src={posterUrl(item.posterPath, 'w342')}
                    alt=""
                    loading="lazy"
                    className={cn(
                      'aspect-[2/3] w-full rounded object-cover',
                      item.ownership === 'owned' ? '' : 'opacity-90',
                    )}
                  />
                  {item.ownership === 'owned' ? (
                    <span className="absolute right-1 top-1 rounded-full bg-primary p-0.5 text-primary-foreground">
                      <Check className="h-3 w-3" />
                    </span>
                  ) : null}
                </div>
                <p className="truncate text-sm font-medium text-foreground" title={item.title}>
                  {item.title}
                </p>
                <p className="text-[11px] text-muted-foreground">
                  {item.releaseDate ?? 'date to be confirmed'}
                </p>
                {item.matchedGenres.length > 0 ? (
                  <p className="truncate text-[11px] text-muted-foreground">
                    {item.matchedGenres.join(' · ')}
                  </p>
                ) : null}
              </div>
            )
            return (
              <li key={item.tmdbId}>
                {item.movieId ? <Link to={`/movies/${item.movieId}`}>{card}</Link> : card}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
