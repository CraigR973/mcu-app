import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Clapperboard, Disc3, Eye, Info, Theater, Ticket } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ProgrammeCoverage, ProgrammeLink } from '@/components/cinemas/ProgrammeCoverage'
import { ProposeTrip } from '@/components/cinemas/ProposeTrip'
import { TripCard } from '@/components/cinemas/TripCard'
import { Poster } from '@/components/movies/Poster'
import { Badge } from '@/components/ui/badge'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { useGoBack } from '@/hooks/useGoBack'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { useProgrammeClock } from '@/hooks/useProgrammeClock'
import { ApiError, fetchCinemaFilm, fetchCinemaTrips, type CinemaFilmDetail } from '@/lib/api'
import { tripsForFilm } from '@/lib/cinema-trips'
import {
  CINEMA_VIEW_PATH,
  cinemaFilmPath,
  clock,
  dayAndDate,
  dayHeading,
  IDENTITY_LABELS,
  listingState,
  londonDate,
  runBadge,
  runReason,
  shortDay,
  shortHorizons,
  shortVenueName,
  showingBooking,
  showingFormats,
  showingScreen,
  staleCoverage,
  type ProgrammeShowing,
  type ProgrammeVenue,
} from '@/lib/cinemas'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

type Detail = CinemaFilmDetail

function runtime(minutes: number | null): string | null {
  return minutes ? `${String(Math.floor(minutes / 60))}h ${String(minutes % 60).padStart(2, '0')}m` : null
}

/** Formats worth a word on a time: "Digital projection" is how almost every film is shown, so it
 *  is said once for the cinema instead. Provider enum syntax never shows (AB7). */
function chipDetails(showing: ProgrammeShowing): string {
  const formats = showingFormats(showing.formats).filter((format) => format !== 'Digital projection')
  return [...formats, showing.screen ? showingScreen(showing.screen) : null].filter(Boolean).join(' · ')
}

function TimeChip({ showing, venue, now, connected, onLapsed }: {
  showing: ProgrammeShowing; venue: ProgrammeVenue; now: number; connected: boolean; onLapsed: () => void
}) {
  const time = clock(showing.startsAtUtc)
  const details = chipDetails(showing)
  const booking = showingBooking(showing, venue, now, connected)
  const label = `${time}${details ? ` ${details}` : ''}`
  if (booking) {
    return (
      <li>
        <a
          href={booking}
          target="_blank"
          rel="noopener noreferrer"
          referrerPolicy="no-referrer"
          aria-label={`${label}, check tickets at ${venue.name}`}
          className="touch-target flex min-h-12 min-w-[5.5rem] flex-col justify-center rounded-md border border-primary/45 bg-primary/5 px-3 py-1.5 text-foreground transition-colors hover:border-primary hover:bg-primary/15"
          onClick={(event) => {
            // The page may have sat open since it was drawn: check again as it is tapped.
            if (!showingBooking(showing, venue, Date.now(), connected)) {
              event.preventDefault()
              onLapsed()
            }
          }}
        >
          <span className="flex items-center justify-between gap-2">
            <span className="text-base font-semibold leading-5 tabular-nums">{time}</span>
            <Ticket className="h-3.5 w-3.5 text-primary" aria-hidden />
          </span>
          {details ? <span className="text-xs leading-4 text-muted-foreground">{details}</span> : null}
        </a>
      </li>
    )
  }
  const stale = showing.observationStale || now - Date.parse(showing.lastSeenUtc) >= 30 * 3600000
  const why = showing.confirmation === 'unconfirmed' ? 'Unconfirmed' : stale ? 'Saved showing is stale' : 'No ticket link'
  return (
    <li>
      <span
        aria-label={`${label}, ${showing.confirmation === 'unconfirmed' ? 'showing unconfirmed' : why.toLowerCase()}`}
        className="flex min-h-12 min-w-[5.5rem] flex-col justify-center rounded-md border border-dashed border-border px-3 py-1.5"
      >
        <span className="text-base font-semibold leading-5 tabular-nums text-muted-foreground">{time}</span>
        {details ? <span className="text-xs leading-4 text-muted-foreground">{details}</span> : null}
        <span className="text-xs leading-4 text-muted-foreground">{why}</span>
      </span>
    </li>
  )
}

interface CinemaDay { venue: ProgrammeVenue; showings: ProgrammeShowing[] }

/** Showings by day, then by cinema in the order each first shows that day. */
function byDayThenCinema(venueList: ProgrammeVenue[], showings: ProgrammeShowing[]): [string, CinemaDay[]][] {
  const venues = new Map(venueList.map((venue) => [venue.id, venue]))
  const days = new Map<string, Map<string, CinemaDay>>()
  for (const showing of showings) {
    const venue = venues.get(showing.venueId)
    if (!venue) continue
    const day = londonDate(Date.parse(showing.startsAtUtc))
    const cinemas = days.get(day) ?? new Map<string, CinemaDay>()
    const group = cinemas.get(venue.id) ?? { venue, showings: [] }
    group.showings.push(showing)
    cinemas.set(venue.id, group)
    days.set(day, cinemas)
  }
  return [...days.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([day, cinemas]) => [day, [...cinemas.values()]])
}

function coverageNote(venue: ProgrammeVenue, day: string, now: number): string | null {
  const coverage = venue.coverage.find((item) => item.localDate === day)
  if (!coverage) return null
  if (coverage.status === 'failed') return 'Latest check failed · ticket links paused'
  if (coverage.status === 'stale' || (coverage.lastSuccessUtc && now - Date.parse(coverage.lastSuccessUtc) >= 30 * 3600000)
    || (coverage.upstreamUtc && now - Date.parse(coverage.upstreamUtc) >= 36 * 3600000)) return 'Saved listing is stale · ticket links paused'
  return null
}

const KIND_ICON = { film: Clapperboard, listing: Clapperboard, event: Theater } as const

/** AC5: the reader's upcoming trips whose address is this page's or whose showing is on it, so
 *  a trip proposed on a listing still shows once a morning links the film. */
function YourTrips({ detail }: { detail: Detail }) {
  const { profile } = useAuth()
  const trips = useQuery({ queryKey: ['cinema-trips', profile?.id], queryFn: fetchCinemaTrips, enabled: Boolean(profile) })
  const mine = tripsForFilm(trips.data?.upcoming ?? [], detail.film.key, new Set(detail.showings.map((showing) => showing.id)))
  if (mine.length === 0) return null
  return (
    <section aria-labelledby="your-trips" className="space-y-1">
      <h2 id="your-trips" className="section-heading text-lg">Your trips</h2>
      <ul className="divide-y divide-border">{mine.map((trip) => <li key={trip.id}><TripCard trip={trip} /></li>)}</ul>
    </section>
  )
}

/** "Vue St Enoch lists only to Fri 6 Nov; ODEON Braehead only to Wed 11 Nov". */
function horizonPhrase(groups: { day: string; venues: ProgrammeVenue[] }[]): string {
  return groups.map(({ day, venues }, index) => {
    const verb = index > 0 ? '' : venues.length === 1 ? 'lists ' : 'list '
    return `${venues.map(shortVenueName).join(' and ')} ${verb}only to ${dayAndDate(day)}`
  }).join('; ')
}

/**
 * One film at the cinema — AC4 (#335, point 3). Every showing across the nine, by day and then
 * by cinema, each time a chip with its format that opens the cinema's own page to check
 * tickets. The address is stable: `tmdb-<id>` for a film, `listing-<id>` for a cinema's listing,
 * which opens the film once a morning's matching links it. Since AC5 (#345) a trip is proposed
 * from its times, and the reader's trips to it sit above them.
 */
export default function CinemaFilmPage() {
  const { key = '' } = useParams()
  const { profile } = useAuth()
  const online = useOnlineStatus()
  const [now, tick] = useProgrammeClock()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const goBack = useGoBack(CINEMA_VIEW_PATH)
  // The person and the film are in the key: never another person's marks, nor another film's
  // ticket links while this one loads.
  const query = useQuery({
    queryKey: ['cinema-film', profile?.id, key],
    queryFn: () => fetchCinemaFilm(key),
    enabled: Boolean(profile) && Boolean(key),
    // Listings change each morning; a minute's freshness lets a linked listing hand its answer
    // to the film's address below without asking again.
    staleTime: 60_000,
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  })
  const detail = query.data

  // A listing matched since its link was made opens as the film, under the film's address.
  useEffect(() => {
    if (!detail || !profile || detail.film.key === key) return
    queryClient.setQueryData(['cinema-film', profile.id, detail.film.key], detail)
    navigate(cinemaFilmPath(detail.film.key), { replace: true })
  }, [detail, key, navigate, profile, queryClient])

  const connected = online && !query.isError
  const today = londonDate(now)
  const notFound = query.error instanceof ApiError && query.error.status === 404

  // No page title is announced: the phone's top bar says "At the cinema" (`titleForPath`), as it
  // says "Film" over a film the collection does not hold, and the film's name is the heading.
  return (
    <div className="page-shell-narrow space-y-6">
      <button type="button" onClick={goBack} className="hidden min-h-11 items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground lg:inline-flex">
        <ArrowLeft className="h-4 w-4" aria-hidden /> At the cinema
      </button>

      {!detail && !query.isError ? <StatePanel tone={online ? 'loading' : 'offline'} title={online ? 'Loading the showings' : 'This film’s showings need a connection'} /> : null}
      {notFound ? (
        <StatePanel
          tone="empty"
          title="Not listed at your cinemas"
          description="This film or listing is not in the programme now."
          action={<Link to={CINEMA_VIEW_PATH} className="font-semibold text-primary hover:underline">See what is on</Link>}
        />
      ) : query.isError && !detail ? (
        <StatePanel tone="error" title="The showings could not be loaded" description={queryErrorMessage(query.error, 'Try again when connected.')} />
      ) : null}

      {detail && detail.film.key === key ? <FilmShowings detail={detail} now={now} today={today} online={online} connected={connected} onLapsed={tick} isAdmin={profile?.role === 'admin'} /> : null}
    </div>
  )
}

function FilmShowings({ detail, now, today, online, connected, onLapsed, isAdmin }: {
  detail: Detail; now: number; today: string; online: boolean; connected: boolean; onLapsed: () => void; isAdmin: boolean
}) {
  const { film } = detail
  // A time that has started leaves the page, as it leaves the list, without a new answer.
  const showings = detail.showings.filter((showing) => Date.parse(showing.startsAtUtc) > now)
  const days = byDayThenCinema(detail.venues, showings)
  const venueIds = [...new Set(showings.map((showing) => showing.venueId))]
  const next = showings[0]
  const nextVenue = next ? detail.venues.find((venue) => venue.id === next.venueId) : undefined
  // A reason, or a listing title, the showings share is said once for the film; where they
  // differ, each cinema's own is said by its times.
  const reasons = [...new Set(detail.showings.map(runReason))]
  const oneReason = reasons.length === 1 ? reasons[0] : null
  const titles = [...new Set(detail.showings.map((showing) => showing.sourceTitle))]
  const oneTitle = titles.length === 1 ? titles[0] : null
  const badges = [...new Set(detail.showings.map((showing) => runBadge(showing.releaseCategory, showing.categoryReason)).filter(Boolean))]
  const filmVenues = detail.venues.filter((venue) => detail.showings.some((showing) => showing.venueId === venue.id))
  // The cinemas showing it that list fewer days than the fortnight: more times may follow there.
  const shortHere = shortHorizons(detail).to
    .map(({ day, venues }) => ({ day, venues: venues.filter((venue) => venueIds.includes(venue.id)) }))
    .filter(({ venues }) => venues.length > 0)
  const Icon = KIND_ICON[film.kind]
  const facts = [film.originalYear ? String(film.originalYear) : null, runtime(film.runtimeMinutes), film.directors.length ? `Directed by ${film.directors.join(' and ')}` : null].filter(Boolean)

  return (
    <article aria-label={film.title} className="space-y-6">
      <header className="flex gap-4">
        {film.kind === 'film' ? (
          <Poster path={film.posterPath} title={film.title} size="w185" eager className="h-40 w-[6.75rem] shrink-0 rounded-md border border-border" />
        ) : (
          <span aria-hidden className="flex h-40 w-[6.75rem] shrink-0 items-center justify-center rounded-md border border-border bg-muted text-muted-foreground">
            <Icon className="h-8 w-8" />
          </span>
        )}
        <div className="min-w-0 space-y-1.5">
          <p className="page-kicker">{film.kind === 'film' ? 'At the cinema' : listingState(film)}</p>
          <h1 className="font-display text-2xl font-semibold leading-tight text-foreground">{film.title}</h1>
          {facts.length ? <p className="text-sm text-muted-foreground">{facts.join(' · ')}</p> : null}
          <div className="flex flex-wrap gap-1.5">
            {badges.map((badge) => <Badge key={badge} tone={badge === 'Rerun' ? 'neutral' : 'primary'}>{badge}</Badge>)}
            {film.watched ? <Badge tone="success"><Eye className="mr-1 h-3 w-3" aria-hidden />Seen</Badge> : null}
            {film.owned ? <Badge tone="info"><Disc3 className="mr-1 h-3 w-3" aria-hidden />Owned</Badge> : null}
          </div>
        </div>
      </header>

      {film.kind !== 'film' ? (
        <section aria-label="Which film this is" className="space-y-2 rounded-md border border-border bg-muted/50 p-3 text-sm">
          <p className="font-semibold">{film.kind === 'event' ? 'An event or double bill, not one film' : IDENTITY_LABELS[film.identityStatus]}</p>
          {film.kind === 'listing' ? (
            <p className="text-muted-foreground">
              This is one cinema chain’s own listing{film.identityReason ? ` (${film.identityReason})` : ''}, so other cinemas’ listings of this title are separate until it is matched to one film.
            </p>
          ) : null}
          {film.identityStatus === 'review' && isAdmin ? (
            <Link to="/identify" className="inline-flex min-h-11 items-center font-semibold text-primary hover:underline">Check which film this is</Link>
          ) : null}
        </section>
      ) : null}

      {/* What the film is to the reader, where it is on next, and why its run is what it is. */}
      <div className="space-y-1.5 text-sm">
        {next ? (
          <p>
            Showing at {venueIds.length === 1 ? (nextVenue?.name ?? '1 cinema') : `${String(venueIds.length)} cinemas`} · next {shortDay(londonDate(Date.parse(next.startsAtUtc)), today)} {clock(next.startsAtUtc)}{venueIds.length > 1 && nextVenue ? `, ${shortVenueName(nextVenue)}` : ''}
          </p>
        ) : null}
        {oneReason ? <p className="text-muted-foreground">{oneReason}</p> : null}
        {oneTitle && oneTitle !== film.title ? <p className="text-xs text-muted-foreground">Listed as “{oneTitle}”</p> : null}
        {film.owned !== null || film.watched !== null ? (
          <p className="flex flex-wrap items-center gap-x-4">
            <span>{film.owned ? 'In the collection' : 'Not in the collection'} · {film.watched ? 'You have watched this' : 'You have not watched this'}</span>
            {film.movieId ? <Link to={`/movies/${film.movieId}`} className="list-link font-semibold text-primary hover:underline">Open in the archive</Link> : null}
          </p>
        ) : film.tmdbId ? (
          <Link to={`/films/tmdb/${String(film.tmdbId)}`} className="list-link font-semibold text-primary hover:underline">About the film</Link>
        ) : null}
      </div>

      {/* AC5 (#345): a trip from this page's times, and the reader's trips to this film. */}
      <ProposeTrip detail={detail} now={now} today={today} online={online} />
      <YourTrips detail={detail} />

      {!next ? (
        <StatePanel compact tone="empty" title="No showings listed now" description="Nothing is listed for this film at your cinemas in the next fortnight." action={<Link to={CINEMA_VIEW_PATH} className="font-semibold text-primary hover:underline">See what is on</Link>} />
      ) : null}

      {/* What holds the times back, then how to read them. */}
      <div className="space-y-2">
        {!online ? <p role="status" className="rounded-md border border-border bg-muted p-3 text-sm">Offline · saved programme only. Ticket links are paused; use an official programme when connected.</p> : null}
        {staleCoverage(filmVenues, now) ? <p role="status" className="rounded-md border border-border bg-muted p-3 text-sm">Some saved programmes are stale or their latest check failed. Ticket links are paused for the dates affected.</p> : null}
        {shortHere.length ? (
          <p className="flex gap-2 text-xs leading-5 text-muted-foreground">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
            <span>{horizonPhrase(shortHere)}, so later times there may follow.</span>
          </p>
        ) : null}
        {days.length ? <p className="text-xs text-muted-foreground">Each time opens the cinema’s own page to check tickets.</p> : null}
      </div>
      {days.map(([day, cinemas]) => (
        <section key={day} aria-labelledby={`day-${day}`} className="space-y-3">
          <h2 id={`day-${day}`} className="section-heading text-lg">{dayHeading(day, today)}</h2>
          <ul className="space-y-4">
            {cinemas.map(({ venue, showings: times }) => {
              const own = [...new Set(times.map(runReason))]
              const listedAs = [...new Set(times.map((showing) => showing.sourceTitle))].filter((title) => title !== film.title)
              const digital = times.some((showing) => showingFormats(showing.formats).includes('Digital projection'))
              const note = coverageNote(venue, day, now)
              return (
                <li key={venue.id} aria-label={venue.name} className="border-t border-border pt-3">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="min-w-0 text-sm font-semibold">{venue.name}</h3>
                    <ProgrammeLink href={venue.officialUrl} className="shrink-0 whitespace-nowrap text-xs">Official programme</ProgrammeLink>
                  </div>
                  <div className="text-xs leading-5 text-muted-foreground">
                    {digital ? <p>Digital projection</p> : null}
                    {listedAs.length && !oneTitle ? <p>Listed as {listedAs.map((title) => `“${title}”`).join(', ')}</p> : null}
                    {!oneReason ? own.filter(Boolean).map((reason) => <p key={reason}>{reason}</p>) : null}
                    {note ? <p className="font-semibold text-foreground">{note}</p> : null}
                  </div>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {times.map((showing) => <TimeChip key={showing.id} showing={showing} venue={venue} now={now} connected={connected} onLapsed={onLapsed} />)}
                  </ul>
                </li>
              )
            })}
          </ul>
        </section>
      ))}

      {detail.alsoListed.length ? (
        <section aria-labelledby="also-listed" className="space-y-2">
          <h2 id="also-listed" className="section-heading text-lg">Also listed under this title</h2>
          <p className="text-xs text-muted-foreground">Maybe the same film listed by another cinema chain, maybe a namesake.</p>
          <ul className="archive-panel divide-y divide-border overflow-hidden">
            {detail.alsoListed.map((other) => (
              <li key={other.key}>
                <Link to={cinemaFilmPath(other.key)} className={cn('flex min-h-12 flex-col justify-center px-4 py-2 hover:bg-muted')}>
                  <span className="text-sm font-semibold">{other.title}</span>
                  <span className="text-xs text-muted-foreground">
                    {other.kind === 'film' ? 'Matched film' : other.kind === 'event' ? 'Event' : 'Not matched yet'} · {other.venueIds.map((id) => detail.venues.find((venue) => venue.id === id)).filter((venue): venue is ProgrammeVenue => Boolean(venue)).map(shortVenueName).join(', ')} · {other.showingCount} {other.showingCount === 1 ? 'showing' : 'showings'}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <ProgrammeCoverage venues={filmVenues.length ? filmVenues : detail.venues} now={now} />
    </article>
  )
}
