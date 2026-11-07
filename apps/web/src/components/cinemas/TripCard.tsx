import type { CinemaTrip } from '@mcu/shared'
import { AlertTriangle, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Poster } from '@/components/movies/Poster'
import { flagWords, REPLY_LABELS, tripLine, tripPath, tripTally } from '@/lib/cinema-trips'

/** What the reader is to this trip, in a few words. */
function yours(trip: CinemaTrip): string {
  if (trip.status === 'cancelled') return 'Cancelled'
  if (trip.proposer.isYou) return 'You’re organising'
  return trip.yourReply ? `You: ${REPLY_LABELS[trip.yourReply]}` : ''
}

/**
 * One cinema trip as a card — AC5 (#345 §6): poster, film, "Mon 9 Nov · 20:10 · ODEON Glasgow
 * Quay", the reader's reply, "1 going · 1 no reply yet" and the flag, opening the trip's page.
 * Movie night lists these, and a film's page lists its own.
 */
export function TripCard({ trip }: { trip: CinemaTrip }) {
  const flag = trip.showing.flag ? flagWords(trip.showing.flag, trip.showing.venueName).line : null
  return (
    <Link
      to={tripPath(trip.id)}
      aria-label={`${trip.filmTitle}, ${tripLine(trip.showing)}`}
      className="flex min-h-14 items-center gap-3 py-3 text-foreground hover:text-primary"
    >
      <Poster path={trip.posterPath} title={trip.filmTitle} size="w92" decorative className="h-16 w-11 shrink-0 rounded-sm border border-border" />
      <span className="min-w-0 flex-1 space-y-0.5">
        <span className="block font-display text-base font-semibold leading-tight">{trip.filmTitle}</span>
        <span className="block text-sm">{tripLine(trip.showing)}</span>
        <span className="block text-xs text-muted-foreground">
          {[yours(trip), trip.status === 'cancelled' ? null : tripTally(trip.counts)].filter(Boolean).join(' · ')}
        </span>
        {flag ? (
          <span className="flex items-center gap-1 text-xs font-semibold text-warning">
            <AlertTriangle className="size-3.5 shrink-0" aria-hidden />{flag}
          </span>
        ) : null}
      </span>
      <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
    </Link>
  )
}
