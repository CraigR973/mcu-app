import { useState } from 'react'
import type { MovieNightSessionList } from '@mcu/shared'
import { withNewNight } from '@/lib/movie-nights'
import { cn, formatDateTime, londonDate } from '@/lib/utils'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, Clapperboard, Link2, Loader2, Popcorn, Sofa, Square } from 'lucide-react'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import { AtTheCinema } from '@/components/cinemas/AtTheCinema'
import { CinemaTrips } from '@/components/cinemas/CinemaTrips'
import { PeoplePicker } from '@/components/cinemas/TripPickers'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import {
  createMovieNight,
  endMovieNight,
  fetchMovieNights,
  joinMovieNight,
  TMDB_GENRES,
  type MovieNightFilters,
} from '@/lib/api'
import { CINEMA_VIEW_PATH } from '@/lib/cinemas'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { shareLink } from '@/lib/share'
import { useAuth } from '@/context/auth'
import type { MovieNightSession } from '@mcu/shared'

type Session = MovieNightSession

/** Ended, or planned for a day already gone: Past screenings (AC4). An open night with no
 *  planned day, or planned for today or later, stays on top. */
function isPast(session: Session, today: string): boolean {
  return session.status === 'ended' || (session.plannedStart !== null && londonDate(Date.parse(session.plannedStart)) < today)
}

function when(session: Session): number {
  return Date.parse(session.plannedStart ?? session.createdAt)
}

const VIEW_LINK = 'touch-target inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-3 text-sm font-semibold transition-colors'

/** AC4: Movie night is two views, at home and at the cinema. Links, so each view has its own
 *  address: the cinema view is the old Cinemas page, and `/cinemas` comes here. */
function Views() {
  return (
    <nav aria-label="Movie night views" className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1">
      <NavLink to="/movie-night" end className={({ isActive }) => cn(VIEW_LINK, isActive ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
        <Sofa className="h-4 w-4" aria-hidden />At home
      </NavLink>
      <NavLink to={CINEMA_VIEW_PATH} className={({ isActive }) => cn(VIEW_LINK, isActive ? 'bg-background text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground')}>
        <Clapperboard className="h-4 w-4" aria-hidden />At the cinema
      </NavLink>
    </nav>
  )
}

/** §8.3 — start a movie night, or join one somebody sent you; since AC4, or go to the cinema. */
export default function MovieNightPage({ view = 'home' }: { view?: 'home' | 'cinema' }) {
  return (
    <div className="page-shell-narrow space-y-6">
      <PageHeader
        eyebrow="Screening room"
        title="Movie night"
        description={view === 'cinema'
          ? 'What is on at your cinemas, film by film, with every showing a tap away.'
          : 'Everyone works through the same shortlist. When you all add the same film, tonight is sorted.'}
      />
      <Views />
      {view === 'cinema' ? <AtTheCinema /> : <AtHome />}
    </div>
  )
}

/** "Mark", "Mark and Sam", "Mark, Sam and Alex". */
function listNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? ''
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1] ?? ''}`
}

/** The filters that matter on the night — AE10 (#355), in place of the year box no night used. */
const SHORTLIST_FILTERS = [
  { key: 'underTwoHours', label: 'Under two hours' },
  { key: 'inNeitherDiary', label: 'In neither diary' },
  { key: 'fourK', label: '4K' },
] as const

type FilterKey = (typeof SHORTLIST_FILTERS)[number]['key']

function AtHome() {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [watching, setWatching] = useState<ReadonlySet<string>>(() => new Set())
  const [ticked, setTicked] = useState<ReadonlySet<FilterKey>>(() => new Set())
  const [genre, setGenre] = useState('')
  const [plannedStart, setPlannedStart] = useState('')
  const [copied, setCopied] = useState<string | null>(null)
  const [copyError, setCopyError] = useState<string | null>(null)

  const sessions = useQuery({ queryKey: ['movie-nights'], queryFn: fetchMovieNights })
  // AE10 (#355), proposal A: who can be sent a night, picked as it starts.
  const people = sessions.data?.people ?? []
  const sendTo = people.filter((person) => watching.has(person.id))

  const start = useMutation({
    mutationFn: () => {
      const filters: MovieNightFilters = {}
      for (const key of ticked) filters[key] = true
      if (genre) filters.genre = genre
      const when = plannedStart ? new Date(plannedStart).toISOString() : undefined
      const ids = sendTo.map((person) => person.id)
      // Only what is set: a night for nobody, unplanned, is still `createMovieNight({})`.
      if (ids.length > 0) return createMovieNight(filters, when, ids)
      return when ? createMovieNight(filters, when) : createMovieNight(filters)
    },
    onSuccess: (session) => {
      // At the top of the list on the phone at once, as well as read again (see movie-nights.ts).
      queryClient.setQueryData<MovieNightSessionList>(['movie-nights'], (list) => withNewNight(list, session))
      void queryClient.invalidateQueries({ queryKey: ['movie-nights'] })
      navigate(`/movie-night/${session.id}`)
    },
  })

  function toggleFilter(key: FilterKey) {
    setTicked((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const finish = useMutation({
    mutationFn: (id: string) => endMovieNight(id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['movie-nights'] }),
  })

  const state = listState(sessions, (sessions.data?.items.length ?? 0) === 0)
  const today = londonDate()
  const items = sessions.data?.items ?? []
  // Open and planned first, the soonest planned at the top; the rest folded away, newest first.
  const upcoming = items.filter((session) => !isPast(session, today)).sort((a, b) => {
    if ((a.plannedStart === null) !== (b.plannedStart === null)) return a.plannedStart === null ? 1 : -1
    return a.plannedStart !== null ? when(a) - when(b) : when(b) - when(a)
  })
  const past = items.filter((session) => isPast(session, today)).sort((a, b) => when(b) - when(a))

  // Batch T4: the phone's share sheet first, copying where there is none. Sending it to
  // the other person as a push is one tap on the night itself.
  async function shareInvite(invitePath: string, sessionId: string) {
    setCopyError(null)
    try {
      const outcome = await shareLink({
        title: 'Movie night',
        text: 'Help pick tonight’s film.',
        url: `${window.location.origin}${invitePath}`,
      })
      setCopied(outcome === 'cancelled' ? null : sessionId)
    } catch (cause) {
      setCopyError(queryErrorMessage(cause, 'The invite link could not be shared.'))
    }
  }

  function row(session: Session) {
    return (
      <li key={session.id} className="flex flex-wrap items-center gap-2 py-3">
        <Link
          to={`/movie-night/${session.id}`}
          className="touch-target flex min-w-0 flex-1 items-center text-sm hover:underline"
        >
          {session.plannedStart ? `Planned ${formatDateTime(session.plannedStart)}` : formatDateTime(session.createdAt)} ·{' '}
          {session.people.length > 1
            ? `with ${session.people.filter((person) => person.id !== profile?.id).map((person) => person.displayName).join(', ')}`
            : session.participantCount === 1 ? 'just you' : `${session.participantCount} people`}
          {session.status === 'ended' ? ' · ended' : ''}
        </Link>
        {session.status === 'open' ? (
          <>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void shareInvite(session.invitePath, session.id)}
            >
              <Link2 className="mr-1 h-3 w-3" aria-hidden />
              {copied === session.id ? 'Shared' : 'Share link'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => finish.mutate(session.id)}
              disabled={finish.isPending}
            >
              <Square className="mr-1 h-3 w-3" aria-hidden />
              End
            </Button>
          </>
        ) : null}
      </li>
    )
  }

  return (
    <>
      <div className="grid gap-4 md:grid-cols-2">
        <section className="archive-panel p-4 sm:p-5">
          <h2 className="section-heading">Start a screening</h2>
          <form
            className="mt-3 space-y-4"
            onSubmit={(event) => {
              event.preventDefault()
              start.mutate()
            }}
          >
            {/* AE10 (#355), proposal A: who is watching, as "Propose a trip" asks; nobody is
                ticked until you tick them, and whoever is ticked is sent it as it starts. */}
            <fieldset className="space-y-2" aria-busy={state === 'loading'}>
              <legend className="field-label">Who’s watching</legend>
              {state === 'loading' ? (
                // One row, the picker's own height, while the people load: with two people the
                // list is one row, so nothing below it moves when they arrive. A Start tapped
                // as they arrived used to land on the space the button had just left (CI, 11 Nov).
                <ul className="rounded-md border border-border" aria-label="Who can be sent it">
                  <li className="flex min-h-12 items-center pl-3 text-sm text-muted-foreground">Finding who can be sent it…</li>
                </ul>
              ) : (
                <PeoplePicker
                  people={people.map((person) => ({ profileId: person.id, displayName: person.displayName, isYou: false }))}
                  chosen={watching}
                  onChange={setWatching}
                  disabled={start.isPending}
                />
              )}
            </fieldset>
            {/* Proposal B: the filters that matter on the night, in place of the year box. */}
            <fieldset className="space-y-2">
              <legend className="field-label">Tonight’s shortlist</legend>
              <div className="flex flex-wrap gap-2">
                {SHORTLIST_FILTERS.map((filter) => (
                  <label key={filter.key} className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-full border border-input px-3 text-sm has-[:checked]:border-primary has-[:checked]:bg-primary/10">
                    <input type="checkbox" className="size-4 accent-primary" checked={ticked.has(filter.key)} onChange={() => toggleFilter(filter.key)} disabled={start.isPending} />
                    {filter.label}
                  </label>
                ))}
              </div>
              <label className="block text-sm">
                <span className="sr-only">Genre</span>
                <select className="select-control w-full sm:w-64" aria-label="Genre" value={genre} onChange={(event) => setGenre(event.target.value)} disabled={start.isPending}>
                  <option value="">Any genre</option>
                  {TMDB_GENRES.map((option) => <option key={option.id} value={option.name}>{option.name}</option>)}
                </select>
              </label>
            </fieldset>
            <label className="block text-sm">
              <span className="field-label">Planned date and time (optional)</span>
              <Input type="datetime-local" value={plannedStart} onChange={(event) => setPlannedStart(event.target.value)} />
            </label>
            <Button type="submit" disabled={start.isPending}>
              {start.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Popcorn className="mr-2 h-4 w-4" aria-hidden />
              )}
              {/* Batch V3: a night is the shortlist now, with no deck to swipe (#228). AE10:
                  the button says who it goes to, since starting it sends it. */}
              {sendTo.length > 0 ? `Start and send to ${listNames(sendTo.map((person) => person.displayName))}` : 'Start movie night'}
            </Button>
          </form>
          {start.isError ? (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {queryErrorMessage(start.error, 'Could not start a movie night.')}
            </p>
          ) : null}
        </section>

        {/* AC4: beside "Start a screening". AC5's "Propose a trip" is on a film's page there. */}
        <section className="archive-panel flex flex-col p-4 sm:p-5" aria-labelledby="plan-cinema-trip">
          <h2 id="plan-cinema-trip" className="section-heading">Plan a cinema trip</h2>
          <p className="mt-1 flex-1 text-sm text-muted-foreground">What is on at your cinemas this week and coming up, with every showing of each film.</p>
          <Button asChild variant="outline" className="mt-3 self-start">
            <Link to={CINEMA_VIEW_PATH}><Clapperboard className="mr-2 h-4 w-4" aria-hidden />See what’s on</Link>
          </Button>
        </section>
      </div>

      <section className="archive-panel p-4 sm:p-5">
        <h2 className="section-heading">Your screenings</h2>
        {state === 'loading' ? (
          <StatePanel compact className="mt-3" tone="loading" title="Loading screenings" />
        ) : null}
        {state === 'offline' ? (
          <StatePanel
            compact
            className="mt-3"
            tone="offline"
            title="Screenings need the network"
            description="Reconnect to load your shared sessions."
          />
        ) : null}
        {state === 'error' ? (
          <StatePanel
            compact
            className="mt-3"
            tone="error"
            title="Screenings unavailable"
            description={queryErrorMessage(sessions.error, 'Could not load your movie nights.')}
          />
        ) : null}
        {state === 'empty' ? (
          <StatePanel
            compact
            className="mt-3"
            tone="empty"
            title="No screenings yet"
            description="Start one above. Whoever you tick is sent it as it starts."
          />
        ) : null}
        {finish.isError ? (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {queryErrorMessage(finish.error, 'That screening could not be ended.')}
          </p>
        ) : null}
        {copyError ? <p role="alert" className="mt-3 text-sm text-destructive">{copyError}</p> : null}
        {state === 'ready' ? (
          <>
            {upcoming.length > 0 ? (
              <ul aria-label="Open and planned screenings" className="mt-2 divide-y divide-border">{upcoming.map(row)}</ul>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">Nothing open or planned. Start one, or plan a cinema trip.</p>
            )}
            {past.length > 0 ? (
              // AC4: closed by default; the night itself still opens from here.
              <details className="group mt-3 border-t border-border pt-1">
                <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between text-sm font-semibold [&::-webkit-details-marker]:hidden">
                  Past screenings ({past.length})
                  <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
                </summary>
                <ul aria-label="Past screenings" className="divide-y divide-border">{past.map(row)}</ul>
              </details>
            ) : null}
          </>
        ) : null}
      </section>

      {/* AC5 (#345): below the nights; not drawn with no trips. */}
      <CinemaTrips />
    </>
  )
}

/** §8.3's acceptance — *"second user joins via URL"*. */
export function MovieNightJoinPage() {
  const navigate = useNavigate()
  const token = window.location.pathname.split('/').pop() ?? ''
  const join = useQuery({
    queryKey: ['movie-night-join', token],
    queryFn: async () => {
      const session = await joinMovieNight(token)
      navigate(`/movie-night/${session.id}`, { replace: true })
      return session
    },
    // Joining is a write. Retrying it on a failure would be retrying a write, and the
    // failure here is almost always "that invite is not valid" — which retrying cannot fix.
    retry: false,
  })

  return (
    <div className="page-shell-narrow flex min-h-[60dvh] items-center justify-center">
      {join.isPending ? (
        <StatePanel compact tone="loading" title="Joining the screening" />
      ) : join.isError ? (
        <StatePanel
          compact
          tone="error"
          title="Invite unavailable"
          description={queryErrorMessage(join.error, 'That invite is not valid.')}
          action={(
            <Button asChild variant="outline">
              <Link to="/movie-night">Start your own instead</Link>
            </Button>
          )}
        />
      ) : null}
    </div>
  )
}
