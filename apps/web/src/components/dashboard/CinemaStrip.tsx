import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Popcorn } from 'lucide-react'
import { Link } from 'react-router-dom'

import { PosterCard, ShelfRow } from '@/components/dashboard/Shelf'
import { useAuth } from '@/context/auth'
import { fetchCinemaFilms } from '@/lib/api'
import { CINEMA_VIEW_PATH, cinemaFilmPath, runBadge, shortVenueName } from '@/lib/cinemas'
import { cinemaStrip, type HomeLineup } from '@/lib/home-films'

/**
 * Home's "At the cinema" — AC4: a poster strip of this week's films, where AB7 had a line of
 * text. It shares At the cinema's read, so opening the view after Home costs nothing more.
 *
 * Until the cinemas' films have posters — before AC3's morning matching, or when the read fails —
 * it is the way in that it was. Either way the way in is a link called "At the cinema", held
 * back by AB7's guard while Home's first layout is arriving.
 */
export function CinemaStrip({ lineup, settled, homeLayoutPending }: { lineup: HomeLineup; settled: boolean; homeLayoutPending: boolean }) {
  const { profile } = useAuth()
  const [now] = useState(Date.now)
  const query = useQuery({ queryKey: ['cinema-films', profile?.id], queryFn: fetchCinemaFilms, enabled: Boolean(profile) })
  const films = settled ? cinemaStrip(lineup, query.data, now) : []
  const venues = new Map((query.data?.venues ?? []).map((venue) => [venue.id, venue]))
  const hold = (event: React.MouseEvent) => {
    if (homeLayoutPending) event.preventDefault()
  }

  if (films.length === 0) {
    return (
      <Link
        to={CINEMA_VIEW_PATH}
        aria-disabled={homeLayoutPending || undefined}
        onClick={hold}
        className={`archive-panel flex items-center gap-3 p-4 transition-colors ${homeLayoutPending ? 'opacity-60' : 'hover:bg-muted'}`}
        aria-label="At the cinema"
      >
        <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/15 text-primary">
          <Popcorn className="size-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block font-display text-base font-semibold">At the cinema</span>
          <span className="mt-0.5 block text-xs text-muted-foreground">What&apos;s showing this week at your nine cinemas.</span>
        </span>
        <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
      </Link>
    )
  }

  return (
    <section aria-labelledby="home-cinema" className="space-y-3">
      <div className="min-w-0">
        <h2 id="home-cinema" className="section-heading text-lg">
          <Link
            to={CINEMA_VIEW_PATH}
            aria-disabled={homeLayoutPending || undefined}
            onClick={hold}
            className="inline-flex min-h-11 items-center gap-2 hover:text-primary"
          >
            <Popcorn className="h-5 w-5 shrink-0 text-primary" aria-hidden />
            At the cinema
            <ChevronRight className="h-4 w-4 text-muted-foreground" aria-hidden />
          </Link>
        </h2>
        <p className="-mt-1 text-xs leading-5 text-muted-foreground">This week at your nine cinemas.</p>
      </div>
      <ShelfRow label="This week at the cinema">
        {films.map(({ card, run, runReason, venueIds }) => {
          const venue = venueIds.length === 1 ? venues.get(venueIds[0]) : undefined
          const where = venue ? shortVenueName(venue) : `${String(venueIds.length)} cinemas`
          const badge = runBadge(run, runReason)
          return (
            <PosterCard
              key={card.key}
              to={cinemaFilmPath(card.key)}
              title={card.title}
              posterPath={card.posterPath}
              detail={<>{badge ? <span className="block">{badge}</span> : null}<span className="block">{where}</span></>}
              disabled={homeLayoutPending}
            />
          )
        })}
      </ShelfRow>
    </section>
  )
}
