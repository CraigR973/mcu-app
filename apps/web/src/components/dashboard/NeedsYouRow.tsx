import { useQuery } from '@tanstack/react-query'
import { CalendarHeart, ChevronRight, Clapperboard, ListChecks } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { NextScreening, NextTrip } from '@mcu/shared'

import { Poster } from '@/components/movies/Poster'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { fetchNeedsYou } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { needsYouCopy } from '@/lib/needs-you'
import { nextTripWords, tripIsSooner, tripNeedsYouCopy, tripPath } from '@/lib/cinema-trips'
import { formatLondonDateTime } from '@/lib/utils'

/** How many items the row shows before it points at Loans for the rest. */
const SHOWN = 5

/** AC2: the person's next planned screening, beside what needs them, from the same read. */
function NextScreeningCard({ screening }: { screening: NextScreening }) {
  const company = screening.withNames.length > 0 ? `with ${screening.withNames.join(' and ')}` : 'just you so far'
  return (
    <Link
      to={`/movie-night/${screening.sessionId}`}
      className="archive-panel flex min-h-14 items-center gap-3 p-4 text-foreground hover:text-primary"
    >
      <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
        <CalendarHeart className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="metadata-label block">Next screening</span>
        <span className="mt-0.5 block font-display text-base font-semibold">{formatLondonDateTime(screening.plannedStart)}</span>
        <span className="block text-xs text-muted-foreground">
          {company}{screening.matchTitle ? ` · it's a match: ${screening.matchTitle}` : ''}
        </span>
      </span>
      <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
    </Link>
  )
}

/** AC5 (#345, decision 7): the next cinema trip, in the same slot, when it is sooner than the
 *  next planned screening. Read from the same answer, so Home makes no new request. */
function NextTripCard({ trip }: { trip: NextTrip }) {
  const words = nextTripWords(trip)
  return (
    <Link
      to={tripPath(trip.tripId)}
      aria-label={words.sentence}
      className="archive-panel flex min-h-14 items-center gap-3 p-4 text-foreground hover:text-primary"
    >
      <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
        <Clapperboard className="size-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="metadata-label block">Next</span>
        <span className="mt-0.5 block font-display text-base font-semibold">{trip.filmTitle}</span>
        <span className="block text-xs text-muted-foreground">{words.detail}</span>
      </span>
      <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
    </Link>
  )
}

interface Row { key: string; title: string; detail: string; to: string; poster: string | null; film: string; loan: boolean }

/**
 * AC1 (#335): what the person signed in can act on now, at the top of Home, for everyone.
 *
 * The API decides who sees what from the loan rows on every read, so a disc confirmed shelved
 * leaves everyone's row at once. Hidden while it loads and when there is nothing to do; a
 * failed or offline read says so, because a hidden row would read as "nothing needs you".
 * Craig's operational "Needs attention" row is separate and stays his alone. Since AC2 the
 * next planned screening sits with it, from the same read (#337). Since AC5 cinema trips come
 * first, soonest showing first, and the next trip takes the slot when it is sooner (#345).
 */
export function NeedsYouRow() {
  const { profile } = useAuth()
  const query = useQuery({
    queryKey: ['needs-you', profile?.id],
    queryFn: fetchNeedsYou,
    enabled: Boolean(profile),
  })
  const items = query.data?.items ?? []
  const trips = query.data?.trips ?? []
  const screening = query.data?.nextScreening ?? null
  const nextTrip = query.data?.nextTrip ?? null
  const state = listState(query, items.length === 0 && trips.length === 0 && screening === null && nextTrip === null)
  if (!profile || state === 'loading' || state === 'empty') return null
  if (state === 'offline') {
    return <StatePanel compact tone="offline" title="What needs you is not cached here" description="Reconnect to see which discs are waiting on you." />
  }
  if (state === 'error') {
    return (
      <StatePanel
        compact
        tone="error"
        title="Could not check what needs you"
        description={queryErrorMessage(query.error, 'Could not load the discs waiting on you.')}
      />
    )
  }
  const top = tripIsSooner(nextTrip, screening)
    ? <NextTripCard trip={nextTrip} />
    : screening ? <NextScreeningCard screening={screening} /> : null
  if (items.length === 0 && trips.length === 0) return top
  const rows: Row[] = [
    ...trips.map((trip) => ({ ...tripNeedsYouCopy(trip), key: `${trip.kind}:${trip.tripId}:${trip.fromName ?? ''}`, poster: trip.posterPath, film: trip.filmTitle, loan: false })),
    ...items.map((item) => ({ ...needsYouCopy(item), key: `${item.kind}:${item.loanId}`, poster: item.posterPath, film: item.movieTitle, loan: true })),
  ]
  const shown = rows.slice(0, SHOWN)
  const loansHidden = items.length - shown.filter((row) => row.loan).length
  const tripsHidden = trips.length - shown.filter((row) => !row.loan).length
  return (
    <div className="space-y-3">
    <section aria-labelledby="needs-you-heading" className="archive-panel p-4">
      <h2 id="needs-you-heading" className="flex items-center gap-2 font-display text-base font-semibold text-foreground">
        <ListChecks aria-hidden className="size-4 text-primary" />
        Needs you
        {/* The list already says how many; the count is for the eye. */}
        <span aria-hidden className="rounded-full bg-primary/15 px-2 py-0.5 text-xs font-semibold text-primary">
          {rows.length}
        </span>
      </h2>
      <ul className="mt-2 divide-y divide-border">
        {shown.map((row) => (
          <li key={row.key}>
            <Link
              to={row.to}
              className="touch-target flex min-h-14 items-center gap-3 py-2.5 text-foreground hover:text-primary"
            >
              <Poster
                path={row.poster}
                title={row.film}
                size="w92"
                decorative
                className="h-12 w-8 shrink-0 rounded-sm border border-border"
              />
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 text-sm font-semibold">{row.title}</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">{row.detail}</span>
              </span>
              <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
            </Link>
          </li>
        ))}
      </ul>
      {tripsHidden > 0 ? (
        <Link to="/movie-night" className="mt-2 inline-block text-sm font-medium text-primary underline-offset-2 hover:underline">
          See all {trips.length} cinema trips on Movie night
        </Link>
      ) : null}
      {loansHidden > 0 ? (
        <Link to="/loans" className="mt-2 block text-sm font-medium text-primary underline-offset-2 hover:underline">
          See all {items.length} on Loans
        </Link>
      ) : null}
    </section>
    {top}
    </div>
  )
}
