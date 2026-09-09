import { useQuery } from '@tanstack/react-query'
import { Check } from 'lucide-react'
import { Link } from 'react-router-dom'

import { fetchRecommendations, posterUrl } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/**
 * §7.2's recommendations, flagged against the shelf.
 *
 * **Two ownership states, not three.** §7.2 asks for "owned / wanted / unowned" and the
 * wanted list is §3.5 — a table **Batch 18** builds. A "wanted" badge that can never
 * appear is a legend entry pointing at nothing, which is the defect gotcha 5 catalogues.
 *
 * An owned recommendation links to the film already here; an unowned one does not link
 * anywhere, because there is nowhere to go yet. Batch 18 gives it a destination.
 */
export function RecommendationsPanel({ movieId }: { movieId: string }) {
  const recsQuery = useQuery({
    queryKey: ['recommendations', movieId],
    queryFn: () => fetchRecommendations(movieId),
    staleTime: 30 * 60 * 1000,
  })
  const items = recsQuery.data?.items ?? []
  const state = listState(recsQuery, items.length === 0)

  if (state === 'loading') {
    return <p className="text-sm text-muted-foreground">Loading recommendations…</p>
  }
  if (state === 'offline') {
    return (
      <p className="text-sm text-muted-foreground">
        Waiting for the network — recommendations could not be loaded.
      </p>
    )
  }
  if (state === 'error') {
    return (
      <p className="text-sm text-muted-foreground">
        {queryErrorMessage(recsQuery.error, 'Recommendations are unavailable.')}
      </p>
    )
  }
  if (state === 'empty') {
    return (
      <p className="text-sm text-muted-foreground">
        {recsQuery.data?.unavailable
          ? 'TMDB could not be reached, so there are no recommendations to show right now.'
          : 'TMDB has no recommendations for this film.'}
      </p>
    )
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        {recsQuery.data?.ownedCount ?? 0} of {items.length} already on the shelf
      </p>
      <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
        {items.map((item) => {
          const card = (
            <div className="space-y-1">
              <div className="relative">
                <img
                  src={posterUrl(item.posterPath, 'w185')}
                  alt=""
                  loading="lazy"
                  className={cn(
                    'aspect-[2/3] w-full rounded object-cover',
                    item.ownership === 'owned' ? '' : 'opacity-70',
                  )}
                />
                {item.ownership === 'owned' ? (
                  <span className="absolute right-1 top-1 rounded-full bg-primary p-0.5 text-primary-foreground">
                    <Check className="h-3 w-3" />
                  </span>
                ) : null}
              </div>
              <p className="truncate text-xs text-foreground" title={item.title}>
                {item.title}
              </p>
              <p className="text-[11px] text-muted-foreground">{item.year ?? '—'}</p>
            </div>
          )
          return (
            <li key={item.tmdbId}>
              {item.movieId ? <Link to={`/movies/${item.movieId}`}>{card}</Link> : card}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
