import { useQuery } from '@tanstack/react-query'
import { CalendarHeart, ChevronRight, Clapperboard, ListChecks } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { NextScreening, NextTrip } from '@mcu/shared'

import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { fetchAttention, fetchNeedsYou } from '@/lib/api'
import { attentionRows } from '@/lib/attention'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { needsYouRows, type NeedsYouRowData } from '@/lib/needs-you'
import { nextTripWords, tripIsSooner, tripPath } from '@/lib/cinema-trips'
import { NeedsYouList } from './NeedsYouList'
import { formatLondonDateTime } from '@/lib/utils'

/** How many items the row shows before it points at Needs you for the rest. */
const SHOWN = 5

/** Home's five, and any App row past them: what has stopped is never left to "See all" (AF1). */
function shownOnHome(rows: NeedsYouRowData[]): NeedsYouRowData[] {
  return [...rows.slice(0, SHOWN), ...rows.slice(SHOWN).filter((row) => row.kind === 'app')]
}

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

/**
 * AC1 (#335): what the person signed in can act on now, at the top of Home, for everyone.
 *
 * The API decides who sees what from the loan rows on every read, so a disc confirmed shelved
 * leaves everyone's row at once. Hidden while it loads and when there is nothing to do; a
 * failed or offline read says so, because a hidden row would read as "nothing needs you".
 * Craig's operational problems stay his alone (AF1 below). Since AC2 the
 * next planned screening sits with it, from the same read (#337). Since AC5 cinema trips come
 * first, soonest showing first, and the next trip takes the slot when it is sooner (#345).
 * Since AE8 the people who keep the shelves see each other's items too, each saying whose it is,
 * their own first; five show here and Needs you lists every one (#355). Since AF1 (#372) Craig's
 * "Needs attention" is part of it: the app's problems as rows labelled App after his own items,
 * and the lines sent to him, from the attention read Home already makes. Mark never asks for it.
 */
export function NeedsYouRow() {
  const { profile } = useAuth()
  const admin = profile?.role === 'admin'
  const query = useQuery({
    queryKey: ['needs-you', profile?.id],
    queryFn: fetchNeedsYou,
    enabled: Boolean(profile),
  })
  // The same key as Home's own read, so this asks for nothing more. A failed read leaves the App
  // rows out, as it hid Needs attention: Home's other rows say when the archive is unreachable.
  const attention = useQuery({ queryKey: ['attention'], queryFn: fetchAttention, enabled: admin })
  const app = admin && attention.data ? attentionRows(attention.data, profile?.id) : []
  const items = query.data?.items ?? []
  const trips = query.data?.trips ?? []
  const reviews = query.data?.reviews ?? []
  const screening = query.data?.nextScreening ?? null
  const nextTrip = query.data?.nextTrip ?? null
  const state = listState(query, items.length === 0 && trips.length === 0 && reviews.length === 0 && screening === null && nextTrip === null)
  if (!profile || state === 'loading') return null
  if (state === 'empty' && app.length === 0) return null
  if (state === 'offline' || state === 'error') {
    const panel = state === 'offline'
      ? <StatePanel compact tone="offline" title="What needs you is not cached here" description="Reconnect to see which discs are waiting on you." />
      : (
        <StatePanel
          compact
          tone="error"
          title="Could not check what needs you"
          description={queryErrorMessage(query.error, 'Could not load the discs waiting on you.')}
        />
      )
    // What has stopped still shows when only the other read failed.
    return app.length > 0 ? <div className="space-y-3">{panel}<NeedsYouCard rows={app} /></div> : panel
  }
  const top = tripIsSooner(nextTrip, screening)
    ? <NextTripCard trip={nextTrip} />
    : screening ? <NextScreeningCard screening={screening} /> : null
  const rows = needsYouRows({ items, trips, reviews }, profile, app)
  if (rows.length === 0) return top
  return (
    <div className="space-y-3">
      <NeedsYouCard rows={rows} />
      {top}
    </div>
  )
}

function NeedsYouCard({ rows }: { rows: NeedsYouRowData[] }) {
  const shown = shownOnHome(rows)
  return (
    <section aria-labelledby="needs-you-heading" className="archive-panel p-4">
      <h2 id="needs-you-heading" className="flex items-center gap-2 font-display text-base font-semibold text-foreground">
        <ListChecks aria-hidden className="size-4 text-primary" />
        Needs you
        {/* The list already says how many; the count is for the eye. */}
        <span aria-hidden className="rounded-full bg-primary/15 px-2 py-0.5 text-xs font-semibold text-primary">
          {rows.length}
        </span>
      </h2>
      <NeedsYouList rows={shown} className="mt-2" />
      {rows.length > shown.length ? (
        <Link to="/needs-you" className="mt-2 block text-sm font-medium text-primary underline-offset-2 hover:underline">
          See all {rows.length} on Needs you
        </Link>
      ) : null}
    </section>
  )
}
