import { useQuery } from '@tanstack/react-query'
import { ChevronDown } from 'lucide-react'

import { TripCard } from '@/components/cinemas/TripCard'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { fetchCinemaTrips } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/**
 * Movie night's "Cinema trips" — AC5 (#345 §6), below the nights: the reader's upcoming trips,
 * soonest first, then "Past trips (n)" folded, as AC4 folds past screenings. With no trips the
 * section is not drawn. A failed read says so, because a missing section would read as none.
 */
export function CinemaTrips() {
  const { profile } = useAuth()
  const query = useQuery({
    queryKey: ['cinema-trips', profile?.id],
    queryFn: fetchCinemaTrips,
    enabled: Boolean(profile),
    refetchOnWindowFocus: 'always',
  })
  if (query.isError && !query.data) {
    return <StatePanel compact tone="error" title="Cinema trips unavailable" description={queryErrorMessage(query.error, 'Could not load your cinema trips.')} />
  }
  const upcoming = query.data?.upcoming ?? []
  const past = query.data?.past ?? []
  if (upcoming.length === 0 && past.length === 0) return null
  return (
    <section aria-labelledby="cinema-trips" className="archive-panel p-4 sm:p-5">
      <h2 id="cinema-trips" className="section-heading">Cinema trips</h2>
      {upcoming.length > 0 ? (
        <ul aria-label="Upcoming cinema trips" className="mt-1 divide-y divide-border">
          {upcoming.map((trip) => <li key={trip.id}><TripCard trip={trip} /></li>)}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">No trips planned. Pick a time on a film’s page at the cinema.</p>
      )}
      {past.length > 0 ? (
        <details className="group mt-3 border-t border-border pt-1">
          <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between text-sm font-semibold [&::-webkit-details-marker]:hidden">
            Past trips ({past.length})
            <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
          </summary>
          <ul aria-label="Past trips" className="divide-y divide-border">
            {past.map((trip) => <li key={trip.id}><TripCard trip={trip} /></li>)}
          </ul>
        </details>
      ) : null}
    </section>
  )
}
