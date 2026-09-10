import { useQuery } from '@tanstack/react-query'
import { Check, Sparkle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
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
    <div className="page-shell space-y-7">
      <PageHeader
        eyebrow="Repertory programme"
        title="Coming soon"
        description="Forthcoming releases selected from the genres already represented on your shelves."
        meta={releasesQuery.data && releasesQuery.data.basedOnGenres.length > 0 ? (
          <span>Based on {releasesQuery.data.basedOnGenres.join(' · ')}</span>
        ) : undefined}
      />

      {state === 'loading' ? (
        <StatePanel tone="loading" title="Preparing the programme" description="Looking for forthcoming releases that fit this archive…" />
      ) : state === 'offline' ? (
        <StatePanel tone="offline" title="Coming soon is not cached here" description="Reconnect to refresh the release programme for this device." />
      ) : state === 'error' ? (
        <StatePanel
          tone="error"
          title="The release programme is unavailable"
          description={queryErrorMessage(releasesQuery.error, 'Could not load new releases.')}
        />
      ) : state === 'empty' ? (
        <StatePanel
          tone="empty"
          icon={Sparkle}
          title="Nothing suitable is scheduled"
          description="No forthcoming releases match this collection’s genres right now."
        />
      ) : (
        <ul className="grid grid-cols-2 gap-x-3 gap-y-7 sm:grid-cols-3 sm:gap-x-5 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
          {items.map((item) => {
            const card = (
              <article className="group space-y-3">
                <div className="relative overflow-hidden rounded-md border border-border bg-muted shadow-soft">
                  <img
                    src={posterUrl(item.posterPath, 'w342')}
                    alt=""
                    loading="lazy"
                    className={cn(
                      'aspect-[2/3] w-full object-cover transition-opacity',
                      item.ownership === 'owned' ? '' : 'opacity-90',
                    )}
                  />
                  {item.ownership === 'owned' ? (
                    <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full border border-success/40 bg-background/95 px-2 py-1 text-[0.625rem] font-semibold text-success shadow-soft">
                      <Check className="h-3 w-3" aria-hidden />
                      Owned
                    </span>
                  ) : null}
                </div>
                <div>
                  <h2 className="line-clamp-2 text-sm font-semibold leading-5 text-foreground group-hover:text-primary" title={item.title}>
                    {item.title}
                  </h2>
                  <p className="mt-1 text-xs tabular-nums text-muted-foreground">
                    {item.releaseDate ?? 'Date to be confirmed'}
                  </p>
                  {item.matchedGenres.length > 0 ? (
                    <p className="mt-1 truncate text-[0.6875rem] text-muted-foreground">
                      {item.matchedGenres.join(' · ')}
                    </p>
                  ) : null}
                </div>
              </article>
            )
            return (
              <li key={item.tmdbId}>
                {item.movieId ? (
                  <Link to={`/movies/${item.movieId}`} className="block rounded-md">
                    {card}
                  </Link>
                ) : card}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
