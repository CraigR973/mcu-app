import { useState } from 'react'
import { cn, formatDateTime, londonDate } from '@/lib/utils'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, Clapperboard, Link2, Loader2, Popcorn, Sofa, Square } from 'lucide-react'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import { AtTheCinema } from '@/components/cinemas/AtTheCinema'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import {
  createMovieNight,
  endMovieNight,
  fetchMovieNights,
  joinMovieNight,
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
          ? 'What is on at your nine cinemas, film by film, with every showing a tap away.'
          : 'Everyone works through the same shortlist. When you all add the same film, tonight is sorted.'}
      />
      <Views />
      {view === 'cinema' ? <AtTheCinema /> : <AtHome />}
    </div>
  )
}

function AtHome() {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [decadeFrom, setDecadeFrom] = useState('')
  const [plannedStart, setPlannedStart] = useState('')
  const [copied, setCopied] = useState<string | null>(null)
  const [copyError, setCopyError] = useState<string | null>(null)

  const sessions = useQuery({ queryKey: ['movie-nights'], queryFn: fetchMovieNights })

  const start = useMutation({
    mutationFn: () =>
      plannedStart
        ? createMovieNight(decadeFrom ? { decadeFrom: Number(decadeFrom) } : {}, new Date(plannedStart).toISOString())
        : createMovieNight(decadeFrom ? { decadeFrom: Number(decadeFrom) } : {}),
    onSuccess: (session) => {
      void queryClient.invalidateQueries({ queryKey: ['movie-nights'] })
      navigate(`/movie-night/${session.id}`)
    },
  })

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
            className="mt-3 flex flex-wrap items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              start.mutate()
            }}
          >
            <label className="text-sm">
              <span className="field-label">Nothing older than</span>
              <Input
                type="number"
                min={1900}
                max={2100}
                placeholder="any year"
                className="w-32"
                value={decadeFrom}
                onChange={(event) => setDecadeFrom(event.target.value)}
              />
            </label>
            <label className="text-sm">
              <span className="field-label">Planned date and time (optional)</span>
              <Input type="datetime-local" value={plannedStart} onChange={(event) => setPlannedStart(event.target.value)} />
            </label>
            <Button type="submit" disabled={start.isPending}>
              {start.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Popcorn className="mr-2 h-4 w-4" aria-hidden />
              )}
              {/* Batch V3: a night is the shortlist now, with no deck to swipe (#228). */}
              Start movie night
            </Button>
          </form>
          {start.isError ? (
            <p role="alert" className="mt-2 text-sm text-destructive">
              {queryErrorMessage(start.error, 'Could not start a movie night.')}
            </p>
          ) : null}
        </section>

        {/* AC4: beside "Start a screening". AC5's "Propose a trip" follows from a film's times. */}
        <section className="archive-panel flex flex-col p-4 sm:p-5" aria-labelledby="plan-cinema-trip">
          <h2 id="plan-cinema-trip" className="section-heading">Plan a cinema trip</h2>
          <p className="mt-1 flex-1 text-sm text-muted-foreground">What is on at your nine cinemas this week and coming up, with every showing of each film.</p>
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
            description="Start one above, then send it to the other person from the night itself."
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
