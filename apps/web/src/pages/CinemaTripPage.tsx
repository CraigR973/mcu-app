import { useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { CinemaTrip, CinemaTripInvitee } from '@mcu/shared'
import { AlertTriangle, ArrowLeft, CalendarClock, Check, Loader2, Ticket, UserPlus, X } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { PeoplePicker, TripTimes } from '@/components/cinemas/TripPickers'
import { Poster } from '@/components/movies/Poster'
import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import { personPath } from '@/lib/people'
import { useGoBack } from '@/hooks/useGoBack'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'
import { useProgrammeClock } from '@/hooks/useProgrammeClock'
import {
  ApiError,
  cancelCinemaTrip,
  fetchCinemaFilm,
  fetchCinemaTrip,
  fetchInvitablePeople,
  inviteToCinemaTrip,
  keepCinemaTripTime,
  moveCinemaTrip,
  replyToCinemaTrip,
} from '@/lib/api'
import { cinemaFilmPath, londonDate, showingBooking, showingScreen } from '@/lib/cinemas'
import {
  flagWords,
  pickableTimes,
  REPLY_LABELS,
  TRIP_OFFLINE,
  tripErrorMessage,
  tripLine,
  tripTally,
  tripWhen,
  tripFormats,
} from '@/lib/cinema-trips'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

type Picker = 'anotherTime' | 'move' | 'invite' | 'cancel' | null

/**
 * One cinema trip — AC5 (#345 §6), behind sign-in and for the people on it only. The film, the
 * showing as the trip keeps it, Check tickets while the live showing carries a link (AB7's rule),
 * the flag the live programme raises, everyone's reply (the organiser first), the reader's own
 * reply, and the organiser's controls. Every push about the trip opens here.
 *
 * No page title is announced: the phone's top bar says "Cinema trip" (`titleForPath`) and the
 * film's name is the heading.
 */
export default function CinemaTripPage() {
  const { id = '' } = useParams()
  const { profile } = useAuth()
  const goBack = useGoBack('/movie-night')
  const query = useQuery({
    queryKey: ['cinema-trip', profile?.id, id],
    queryFn: () => fetchCinemaTrip(id),
    enabled: Boolean(profile) && Boolean(id),
    // A page left open refreshes when it comes back into view, and after each write.
    refetchOnWindowFocus: 'always',
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 2,
  })
  const online = useOnlineStatus()
  const notFound = query.error instanceof ApiError && query.error.status === 404
  return (
    <div className="page-shell-narrow space-y-6">
      <button type="button" onClick={goBack} className="hidden min-h-11 items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground lg:inline-flex">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Movie night
      </button>
      {!query.data && !query.isError ? <StatePanel tone={online ? 'loading' : 'offline'} title={online ? 'Loading the trip' : 'This trip needs a connection'} /> : null}
      {notFound ? (
        <StatePanel
          tone="empty"
          title="Trip not found"
          description="Only the people on a trip can open it."
          action={<Link to="/movie-night" className="font-semibold text-primary hover:underline">Go to Movie night</Link>}
        />
      ) : query.isError && !query.data ? (
        <StatePanel tone="error" title="The trip could not be loaded" description={queryErrorMessage(query.error, 'Try again when connected.')} />
      ) : null}
      {query.data ? <Trip trip={query.data} online={online} /> : null}
    </div>
  )
}

function Trip({ trip, online }: { trip: CinemaTrip; online: boolean }) {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const [now, tick] = useProgrammeClock()
  const [picker, setPicker] = useState<Picker>(null)
  const [time, setTime] = useState<string | null>(null)
  const [chosen, setChosen] = useState<Set<string>>(new Set())
  const today = londonDate(now)
  const upcoming = trip.status === 'upcoming' && Date.parse(trip.showing.startsAtUtc) > now
  const organiser = trip.proposer.isYou
  const me = trip.invitees.find((person) => person.isYou) ?? null

  const write = useMutation({
    mutationFn: (run: () => Promise<CinemaTrip>) => run(),
    onSuccess: (next) => {
      queryClient.setQueryData(['cinema-trip', profile?.id, trip.id], next)
      void queryClient.invalidateQueries({ queryKey: ['cinema-trips'] })
      setPicker(null)
      setTime(null)
      setChosen(new Set())
    },
    // A refusal ("The trip has moved…") is about a screen out of date: show the trip as it is.
    onError: () => void queryClient.invalidateQueries({ queryKey: ['cinema-trip', profile?.id, trip.id] }),
  })
  const busy = write.isPending || !online
  const film = useQuery({
    queryKey: ['cinema-film', profile?.id, trip.filmKey],
    queryFn: () => fetchCinemaFilm(trip.filmKey),
    enabled: Boolean(profile) && (picker === 'anotherTime' || picker === 'move'),
    staleTime: 60_000,
  })
  // AE6 (#355): asked for the trip's film, so each person says whether they have seen it.
  const people = useQuery({
    queryKey: ['cinema-trip-people', profile?.id, trip.filmKey],
    queryFn: () => fetchInvitablePeople(trip.filmKey),
    enabled: Boolean(profile) && picker === 'invite',
  })

  const { live, venue, flag } = trip.showing
  const booking = upcoming && live && venue ? showingBooking(live, venue, now, online) : null
  const flagged = upcoming && flag ? flagWords(flag, trip.showing.venueName) : null
  const details = [tripFormats(trip.showing.formats), trip.showing.screen ? showingScreen(trip.showing.screen) : null].filter(Boolean).join(' · ')
  // A row the cinema moved to another time is the proposer's to follow: leave it pickable.
  const exclude = flag === 'withdrawn' ? null : trip.showing.showingId
  const times = film.data ? pickableTimes(film.data, now, exclude) : null

  function open(next: Picker) {
    write.reset()
    setTime(null)
    setChosen(new Set())
    setPicker(picker === next ? null : next)
  }

  return (
    <article aria-label={trip.filmTitle} className="space-y-6">
      <header className="flex gap-4">
        <Poster path={trip.posterPath} title={trip.filmTitle} size="w185" eager className="h-40 w-[6.75rem] shrink-0 rounded-md border border-border" />
        <div className="min-w-0 space-y-1.5">
          <p className="page-kicker">{trip.status === 'cancelled' ? 'Cancelled trip' : trip.status === 'past' || !upcoming ? 'Past trip' : 'Cinema trip'}</p>
          <h1 className="font-display text-2xl font-semibold leading-tight text-foreground">{trip.filmTitle}</h1>
          <p className="text-sm font-semibold">{tripLine(trip.showing)}</p>
          {details ? <p className="text-xs text-muted-foreground">{details}</p> : null}
          <Link to={cinemaFilmPath(trip.filmKey)} className="list-link inline-flex min-h-11 items-center text-sm font-semibold text-primary hover:underline">
            Every showing of this film
          </Link>
        </div>
      </header>

      {trip.status === 'cancelled' ? (
        <p role="status" className="rounded-md border border-border bg-muted p-3 text-sm">
          {organiser ? 'You cancelled this trip.' : `${trip.proposer.displayName} cancelled this trip.`}
        </p>
      ) : !upcoming ? (
        <p role="status" className="rounded-md border border-border bg-muted p-3 text-sm">This showing has started.</p>
      ) : null}

      {flagged ? (
        <div role="status" className="flex gap-2 rounded-md border border-warning/35 bg-warning/12 p-3 text-sm">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
          <span>{flagged.line}{organiser && flagged.ask ? ` ${flagged.ask}` : ''}</span>
        </div>
      ) : null}

      {booking ? (
        <Button asChild className="w-full sm:w-auto">
          <a
            href={booking}
            target="_blank"
            rel="noopener noreferrer"
            referrerPolicy="no-referrer"
            onClick={(event) => {
              // The page may have sat open since it was drawn: check again as it is tapped.
              if (!live || !venue || !showingBooking(live, venue, Date.now(), online)) {
                event.preventDefault()
                tick()
              }
            }}
          >
            <Ticket aria-hidden />Check tickets at {trip.showing.venueName}
          </a>
        </Button>
      ) : null}

      <section aria-labelledby="whos-going" className="space-y-2">
        <h2 id="whos-going" className="section-heading text-lg">Who’s going</h2>
        <p className="text-sm text-muted-foreground">{tripTally(trip.counts)}</p>
        <ul className="archive-panel divide-y divide-border overflow-hidden">
          <li className="flex min-h-12 items-center justify-between gap-3 px-4 py-2 text-sm">
            {/* AE9 (#355): a name opens its person's page; your own opens You. */}
            <Link to={personPath(trip.proposer.profileId, trip.proposer.isYou ? trip.proposer.profileId : null)} className="font-semibold hover:text-primary hover:underline">{trip.proposer.displayName}{trip.proposer.isYou ? ' (you)' : ''}</Link>
            <span className="text-muted-foreground">Organising</span>
          </li>
          {trip.invitees.map((person) => (
            <Invitee
              key={person.profileId}
              person={person}
              now={now}
              actions={organiser && upcoming && person.reply === 'anotherTime' && person.suggestion ? (
                <div className="flex flex-wrap gap-2 pt-2">
                  <Button
                    type="button"
                    size="sm"
                    disabled={busy || person.suggestion.flag !== null || person.suggestion.showingId === null || Date.parse(person.suggestion.startsAtUtc) <= now}
                    onClick={() => {
                      const suggestion = person.suggestion
                      if (!suggestion?.showingId) return
                      const showingId = suggestion.showingId
                      write.mutate(() => moveCinemaTrip(trip.id, { revision: trip.revision, showingId, fromProfileId: person.profileId, fromReplyRevision: person.replyRevision }))
                    }}
                  >
                    <Check aria-hidden />Accept this time
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => write.mutate(() => keepCinemaTripTime(trip.id, { profileId: person.profileId, replyRevision: person.replyRevision }))}
                  >
                    Keep this time
                  </Button>
                </div>
              ) : null}
            />
          ))}
        </ul>
      </section>

      {me && upcoming ? (
        <section aria-labelledby="your-reply" className="space-y-3">
          <h2 id="your-reply" className="section-heading text-lg">Your reply</h2>
          <div className="grid grid-cols-3 gap-2">
            {(['going', 'notGoing', 'anotherTime'] as const).map((reply) => (
              <Button
                key={reply}
                type="button"
                variant={me.reply === reply ? 'default' : 'outline'}
                aria-pressed={me.reply === reply}
                disabled={busy}
                className="px-2"
                onClick={() => (reply === 'anotherTime' ? open('anotherTime') : write.mutate(() => replyToCinemaTrip(trip.id, { revision: trip.revision, reply })))}
              >
                {REPLY_LABELS[reply]}
              </Button>
            ))}
          </div>
          {picker === 'anotherTime' ? (
            <TimePanel
              title="Suggest another time"
              times={times}
              loading={film.isPending}
              error={film.isError ? queryErrorMessage(film.error, 'Could not load the film’s times.') : null}
              today={today}
              selected={time}
              onSelect={setTime}
              disabled={busy}
              submit="Suggest this time"
              onSubmit={() => {
                if (time) write.mutate(() => replyToCinemaTrip(trip.id, { revision: trip.revision, reply: 'anotherTime', showingId: time }))
              }}
            />
          ) : null}
        </section>
      ) : null}

      {organiser && upcoming ? (
        <section aria-labelledby="change-trip" className="space-y-3">
          <h2 id="change-trip" className="section-heading text-lg">Change the trip</h2>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant={picker === 'move' ? 'default' : 'outline'} aria-expanded={picker === 'move'} disabled={busy} onClick={() => open('move')}>
              <CalendarClock aria-hidden />Move to another time
            </Button>
            <Button type="button" variant={picker === 'invite' ? 'default' : 'outline'} aria-expanded={picker === 'invite'} disabled={busy} onClick={() => open('invite')}>
              <UserPlus aria-hidden />Invite more
            </Button>
            <Button type="button" variant="outline" aria-expanded={picker === 'cancel'} disabled={busy} onClick={() => open('cancel')}>
              <X aria-hidden />Cancel trip
            </Button>
          </div>
          {picker === 'move' ? (
            <TimePanel
              title="Move the trip to another time"
              note="Everyone is asked again."
              times={times}
              loading={film.isPending}
              error={film.isError ? queryErrorMessage(film.error, 'Could not load the film’s times.') : null}
              today={today}
              selected={time}
              onSelect={setTime}
              disabled={busy}
              submit="Move the trip"
              onSubmit={() => {
                if (time) write.mutate(() => moveCinemaTrip(trip.id, { revision: trip.revision, showingId: time }))
              }}
            />
          ) : null}
          {picker === 'invite' ? (
            <div className="space-y-3 rounded-md border border-border p-3">
              <h3 className="text-sm font-semibold">Invite more people</h3>
              {people.data ? (
                <PeoplePicker
                  people={people.data.people.filter((person) => !trip.invitees.some((invitee) => invitee.profileId === person.profileId))}
                  chosen={chosen}
                  onChange={setChosen}
                  disabled={busy}
                  seenKnown={people.data.seenKnown}
                />
              ) : people.isError ? (
                <p role="alert" className="text-sm text-destructive">{queryErrorMessage(people.error, 'Could not load who you can invite.')}</p>
              ) : (
                <p className="text-sm text-muted-foreground">Loading who you can invite…</p>
              )}
              <Button type="button" disabled={busy || chosen.size === 0} onClick={() => write.mutate(() => inviteToCinemaTrip(trip.id, [...chosen]))}>
                Send invitations
              </Button>
            </div>
          ) : null}
          {picker === 'cancel' ? (
            <div className="space-y-3 rounded-md border border-destructive/30 bg-destructive/10 p-3">
              <p className="text-sm font-semibold">Cancel this trip? Everyone still able to go is told.</p>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="destructive" disabled={busy} onClick={() => write.mutate(() => cancelCinemaTrip(trip.id))}>
                  Cancel the trip
                </Button>
                <Button type="button" variant="outline" onClick={() => setPicker(null)}>Keep it</Button>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {upcoming && (me || organiser) ? (
        <div className="space-y-2" aria-live="polite">
          {!online ? <p role="status" className="text-sm font-semibold">{TRIP_OFFLINE}</p> : null}
          {write.isPending ? <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" aria-hidden />Saving…</p> : null}
          {write.isError ? (
            <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {tripErrorMessage(write.error, 'That change could not be saved.')}
            </p>
          ) : null}
        </div>
      ) : null}
    </article>
  )
}

function Invitee({ person, now, actions }: { person: CinemaTripInvitee; now: number; actions: ReactNode }) {
  const suggestion = person.reply === 'anotherTime' ? person.suggestion : null
  return (
    <li className="px-4 py-2 text-sm">
      <div className="flex min-h-8 items-center justify-between gap-3">
        <Link to={personPath(person.profileId, person.isYou ? person.profileId : null)} className="font-semibold hover:text-primary hover:underline">{person.displayName}{person.isYou ? ' (you)' : ''}</Link>
        <span className={cn(person.reply === 'going' ? 'font-semibold text-success' : 'text-muted-foreground')}>{REPLY_LABELS[person.reply]}</span>
      </div>
      {suggestion ? (
        <p className="text-xs text-muted-foreground">
          Suggests {tripWhen(suggestion.startsAtUtc)}{tripFormats(suggestion.formats) ? ` ${tripFormats(suggestion.formats)}` : ''} · {suggestion.venueName}
          {suggestion.flag !== null || Date.parse(suggestion.startsAtUtc) <= now ? ' · no longer listed' : ''}
        </p>
      ) : null}
      {actions}
    </li>
  )
}

function TimePanel({ title, note, times, loading, error, today, selected, onSelect, disabled, submit, onSubmit }: {
  title: string
  note?: string
  times: ReturnType<typeof pickableTimes> | null
  loading: boolean
  error: string | null
  today: string
  selected: string | null
  onSelect: (id: string) => void
  disabled: boolean
  submit: string
  onSubmit: () => void
}) {
  return (
    <div className="space-y-3 rounded-md border border-border p-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
      {times ? (
        <TripTimes days={times} today={today} selected={selected} onSelect={onSelect} disabled={disabled} />
      ) : error ? (
        <p role="alert" className="text-sm text-destructive">{error}</p>
      ) : loading ? (
        <p className="text-sm text-muted-foreground">Loading the film’s times…</p>
      ) : null}
      <Button type="button" disabled={disabled || selected === null} onClick={onSubmit}>{submit}</Button>
    </div>
  )
}
