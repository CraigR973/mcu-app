import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, CircleDashed, Eye, Link2, Play, Popcorn, Send, X } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import type { MovieNightCandidate, MovieNightMatch, MovieNightSession } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import { Poster } from '@/components/movies/Poster'
import { SuggestFilmPanel } from '@/components/movies/SuggestFilmPanel'
import { useAuth } from '@/context/auth'
import {
  castMovieNightVote,
  fetchMovieNight,
  fetchMovieNightCandidates,
  posterUrl,
  sendMovieNight,
  streamMovieNightEvents,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { shareLink } from '@/lib/share'
import { cn, formatShortDate } from '@/lib/utils'

/** How far a card must travel before it counts as a swipe rather than a wobble. */
const SWIPE_THRESHOLD = 90

/** Arrow keys belong to the field currently being edited, not to the swipe deck behind it. */
function isTextEntryTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return (
    target.matches('input, textarea, select') ||
    target.isContentEditable ||
    target.closest('[contenteditable="true"]') !== null
  )
}

/** "You and Mark", "You, Mark and Sam" — who is in tonight, from where you sit. */
function peopleLine(session: MovieNightSession, you: string | undefined): string {
  const others = session.people.filter((person) => person.id !== you).map((person) => person.displayName)
  if (others.length === 0) return 'Just you so far'
  if (others.length === 1) return `You and ${others[0]}`
  return `You, ${others.slice(0, -1).join(', ')} and ${others[others.length - 1]}`
}

function VoteChip({ vote }: { vote: boolean | null }) {
  if (vote === true) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-success/12 px-2 py-0.5 text-xs font-semibold text-success">
        <Check className="h-3.5 w-3.5" aria-hidden /> Added
      </span>
    )
  }
  if (vote === false) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
        <X className="h-3.5 w-3.5" aria-hidden /> Skipped
      </span>
    )
  }
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs font-semibold text-muted-foreground">
      <CircleDashed className="h-3.5 w-3.5" aria-hidden /> Not voted
    </span>
  )
}

/**
 * Who tonight can be sent to, and the link — Batch T4, snag 11.
 *
 * "Send to Mark" is one tap: it puts him in the night and pushes a notification that opens
 * this night. The link stays as the backup, through the phone's share sheet.
 */
function InviteBar({ session, you }: { session: MovieNightSession; you: string | undefined }) {
  const queryClient = useQueryClient()
  const [shared, setShared] = useState<string | null>(null)
  const send = useMutation({
    mutationFn: (userId: string) => sendMovieNight(session.id, [userId]),
    onSuccess: (updated) => queryClient.setQueryData(['movie-night', session.id], updated),
  })
  const share = useMutation({
    mutationFn: () =>
      shareLink({
        title: 'Movie night',
        text: 'Help pick tonight’s film.',
        url: `${window.location.origin}${session.invitePath}`,
      }),
    onSuccess: (outcome) => setShared(outcome === 'copied' ? 'Link copied.' : outcome === 'shared' ? 'Link shared.' : null),
  })
  const sentTo = session.people.filter((person) => person.invited && person.id !== you)

  return (
    <section className="flex flex-wrap items-center gap-2" aria-label="Invite">
      {session.invitable.map((person) => (
        <Button key={person.id} type="button" onClick={() => send.mutate(person.id)} disabled={send.isPending}>
          <Send className="h-4 w-4" aria-hidden /> Send to {person.displayName}
        </Button>
      ))}
      {sentTo.map((person) => (
        <span key={person.id} className="inline-flex items-center gap-1 text-sm font-semibold text-success">
          <Check className="h-4 w-4" aria-hidden /> Sent to {person.displayName}
        </span>
      ))}
      <Button type="button" variant="outline" onClick={() => share.mutate()} disabled={share.isPending}>
        <Link2 className="h-4 w-4" aria-hidden /> Share link
      </Button>
      {shared ? <span role="status" className="text-xs text-muted-foreground">{shared}</span> : null}
      {send.isError ? (
        <p role="alert" className="w-full text-sm text-destructive">{queryErrorMessage(send.error, 'It could not be sent.')}</p>
      ) : null}
      {share.isError ? (
        <p role="alert" className="w-full text-sm text-destructive">{queryErrorMessage(share.error, 'The link could not be shared.')}</p>
      ) : null}
    </section>
  )
}

/** Where a film on the list opens: its page if it has one here, its card if not. */
function filmPath(card: MovieNightCandidate): string | null {
  if (card.movieId) return `/movies/${card.movieId}`
  if (card.tmdbId) return `/films/tmdb/${String(card.tmdbId)}`
  return null
}

/**
 * Tonight's shortlist — Batch T4, snag 10b.
 *
 * **Opening a night shows the list**, not one card. The deck showed a single film and a
 * count, and the list everyone was building was never visible as a list. Your own vote is
 * shown on each film; **the other person's never is** (#157) — seeing their answer first
 * changes the game.
 */
function Shortlist({ cards, onStart }: { cards: MovieNightCandidate[]; onStart: () => void }) {
  const toVote = cards.filter((card) => card.myVote === null).length
  return (
    <section className="space-y-3" aria-labelledby="shortlist-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="shortlist-heading" className="section-heading text-base">
          Tonight's shortlist <span className="font-sans text-sm font-normal text-muted-foreground">· {cards.length} films</span>
        </h2>
        {toVote > 0 ? (
          <Button type="button" onClick={onStart}>
            <Play className="h-4 w-4" aria-hidden /> Start swiping ({toVote})
          </Button>
        ) : (
          <span className="text-sm text-muted-foreground">You've voted on every film.</span>
        )}
      </div>
      <ul className="archive-panel divide-y divide-border overflow-hidden">
        {cards.map((card) => {
          const path = filmPath(card)
          const body = (
            <>
              <Poster path={card.posterPath} title={card.title} size="w92" decorative className="h-16 w-11 shrink-0 rounded-sm" />
              <span className="min-w-0 flex-1">
                <span className="flex min-w-0 items-baseline gap-2">
                  <span className="truncate text-sm font-semibold text-foreground">{card.title}</span>
                  {card.year ? <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{card.year}</span> : null}
                </span>
                <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                  {card.suggestedBy ? `Suggested by ${card.suggestedBy}` : 'From the Archive'}
                  {card.movieId ? '' : card.streamingOn.length > 0 ? ` · on ${card.streamingOn.join(', ')}` : ' · not on the shelf'}
                </span>
              </span>
              <VoteChip vote={card.myVote} />
            </>
          )
          return (
            <li key={card.suggestionId}>
              {path ? (
                <Link to={path} className="flex min-h-16 items-center gap-3 px-3 py-2 hover:bg-muted">{body}</Link>
              ) : (
                <div className="flex min-h-16 items-center gap-3 px-3 py-2">{body}</div>
              )}
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/**
 * §8.4 — a movie night: the shortlist, the swipe deck, and sending it to the other person.
 *
 * **The other person's votes are never shown.** The event stream says only that *a* vote
 * happened, and the deck is filtered by this person's own votes — a card vanishing because
 * they swiped it would leak which way they went.
 *
 * Gestures are pointer events rather than a drag library: pointer events cover mouse,
 * touch and pen in one API. Keyboard works too, in the deck, because a gesture-only
 * control is one nobody can use on a laptop.
 */
export default function MovieNightSessionPage() {
  const { id = '' } = useParams()
  const { profile } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [view, setView] = useState<'list' | 'deck'>('list')
  const [index, setIndex] = useState(0)
  const [drag, setDrag] = useState(0)
  const [match, setMatch] = useState<MovieNightMatch | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [realtimeError, setRealtimeError] = useState<string | null>(null)
  const startX = useRef<number | null>(null)

  const session = useQuery({
    queryKey: ['movie-night', id],
    queryFn: () => fetchMovieNight(id),
    enabled: Boolean(id),
  })
  const deck = useQuery({
    queryKey: ['movie-night-candidates', id],
    queryFn: () => fetchMovieNightCandidates(id),
    enabled: Boolean(id),
  })

  // §8.4's realtime half. A match found by the *other* person's swipe arrives here, and
  // since Batch T4 so does a film they suggest, so the list is the same on both phones.
  useEffect(() => {
    if (!id) return
    let cancelled = false
    void (async () => {
      try {
        for await (const event of streamMovieNightEvents(id)) {
          if (cancelled) return
          setRealtimeError(null)
          if (event.kind === 'match' && event.movieId && event.title) {
            setMatch({
              movieId: event.movieId,
              title: event.title,
              posterPath: event.posterPath ?? null,
            })
          } else if (event.kind === 'joined' || event.kind === 'ended') {
            void queryClient.invalidateQueries({ queryKey: ['movie-night', id] })
          } else if (event.kind === 'suggestion') {
            void queryClient.invalidateQueries({ queryKey: ['movie-night-candidates', id] })
          }
        }
      } catch (cause) {
        if (!cancelled) {
          setRealtimeError(
            queryErrorMessage(cause, 'Live updates were interrupted. Your voting controls still work.'),
          )
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [id, queryClient])

  const cards = deck.data?.items ?? []
  const deckState = listState(deck, cards.length === 0)
  const undecided = cards.filter((card) => card.myVote === null)
  const current: MovieNightCandidate | undefined = undecided[index]

  const vote = useCallback(
    async (liked: boolean) => {
      if (!current || busy) return
      setBusy(true)
      setError(null)
      setDrag(0)
      try {
        const result = await castMovieNightVote(id, current.suggestionId, liked)
        if (result.match) setMatch(result.match)
        setIndex((value) => value + 1)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'That swipe did not register.')
      } finally {
        setBusy(false)
      }
    },
    [busy, current, id],
  )

  const backToList = useCallback(() => {
    setView('list')
    setIndex(0)
    // The list shows your votes, so it re-reads them rather than trusting the deck's count.
    void queryClient.invalidateQueries({ queryKey: ['movie-night-candidates', id] })
  }, [id, queryClient])

  // Keyboard, in the deck only: on the list there is no single film an arrow would mean.
  useEffect(() => {
    if (view !== 'deck') return
    const onKey = (event: KeyboardEvent) => {
      if (
        match ||
        !current ||
        busy ||
        event.defaultPrevented ||
        event.metaKey ||
        event.ctrlKey ||
        event.altKey ||
        isTextEntryTarget(event.target)
      ) return
      if (event.key === 'ArrowRight') {
        event.preventDefault()
        void vote(true)
      }
      if (event.key === 'ArrowLeft') {
        event.preventDefault()
        void vote(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, current, match, view, vote])

  if (session.isError) {
    return (
      <div className="page-shell-narrow">
        <StatePanel
          tone="error"
          title="Screening unavailable"
          description={queryErrorMessage(session.error, 'That movie night could not be loaded.')}
          action={(
            <Button asChild variant="outline">
              <Link to="/movie-night">Back to movie night</Link>
            </Button>
          )}
        />
      </div>
    )
  }

  if (session.fetchStatus === 'paused' && session.data === undefined) {
    return (
      <div className="page-shell-narrow">
        <StatePanel
          tone="offline"
          title="Screening needs the network"
          description="Reconnect to load this shared session."
        />
      </div>
    )
  }

  const night = session.data
  const open = night?.status === 'open'

  return (
    <div className="mx-auto flex max-w-md flex-col gap-4 px-4 pb-24 pt-4 sm:px-6 lg:pt-6">
      {/* A desktop back link and heading: on a phone the top bar has both (Batch T3). */}
      <Link to="/movie-night" className="hidden min-h-11 items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground lg:inline-flex">
        <ArrowLeft className="h-4 w-4" aria-hidden /> All movie nights
      </Link>
      <header className="space-y-1">
        <h1 className="hidden items-center gap-2 font-display text-2xl font-semibold lg:flex">
          <Popcorn className="h-5 w-5" aria-hidden />
          Movie night
        </h1>
        {night ? (
          <p className="text-sm text-muted-foreground">
            {peopleLine(night, profile?.id)} · {formatShortDate(night.createdAt)}
            {night.status === 'ended' ? ' · this one has ended' : ''}
          </p>
        ) : null}
      </header>

      {night && open ? <InviteBar session={night} you={profile?.id} /> : null}

      {realtimeError ? (
        <p role="status" className="w-full rounded-md border border-warning/45 bg-warning/10 p-3 text-sm text-foreground">
          {realtimeError}
        </p>
      ) : null}

      {match ? (
        <div role="status" className="w-full rounded-lg border-2 border-success bg-success/10 p-6 text-center">
          <Check className="mx-auto h-8 w-8 text-success" aria-hidden />
          <p className="mt-2 text-lg font-bold">It's a match</p>
          <p className="mt-1 text-xl">{match.title}</p>
          {match.posterPath ? (
            <img src={posterUrl(match.posterPath)} alt="" className="mx-auto mt-3 w-32 rounded shadow" />
          ) : null}
          <div className="mt-4 flex justify-center gap-2">
            <Button variant="outline" onClick={() => setMatch(null)}>
              Keep going
            </Button>
            <Button onClick={() => navigate('/movie-night')}>Done</Button>
          </div>
        </div>
      ) : deckState === 'loading' ? (
        <StatePanel className="w-full" tone="loading" title="Preparing the shortlist" />
      ) : deckState === 'offline' ? (
        <StatePanel className="w-full" tone="offline" title="The shortlist needs the network" description="Reconnect to load the films in this screening." />
      ) : deckState === 'error' ? (
        <StatePanel
          className="w-full"
          tone="error"
          title="Shortlist unavailable"
          description={queryErrorMessage(deck.error, 'The films for this screening could not be loaded.')}
        />
      ) : deckState === 'empty' ? (
        <StatePanel
          className="w-full"
          tone="empty"
          title="No films on the list yet"
          description="Suggest one below, or start another night with a wider year range."
        />
      ) : view === 'list' ? (
        <Shortlist cards={cards} onStart={() => { setIndex(0); setView('deck') }} />
      ) : !current ? (
        <StatePanel
          className="w-full"
          tone="empty"
          title="You've voted on every film"
          description="There's no match yet. Suggest another, or wait for the others to vote."
          action={<Button variant="outline" onClick={backToList}>Back to the list</Button>}
        />
      ) : (
        <>
          <button type="button" onClick={backToList} className="inline-flex min-h-11 items-center gap-2 self-start text-sm font-semibold text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" aria-hidden /> Back to the list
          </button>
          <div
            role="group"
            aria-label={`${current.title}. Swipe right to add it, left to skip it.`}
            className={cn(
              'w-full select-none rounded-xl border border-border bg-card p-4 shadow-soft',
              'touch-pan-y transition-transform',
              busy && 'opacity-60',
            )}
            style={{
              transform: `translateX(${drag}px) rotate(${drag / 25}deg)`,
              transition: startX.current === null ? 'transform 150ms' : 'none',
            }}
            onPointerDown={(event) => {
              startX.current = event.clientX
              event.currentTarget.setPointerCapture(event.pointerId)
            }}
            onPointerMove={(event) => {
              if (startX.current === null) return
              setDrag(event.clientX - startX.current)
            }}
            onPointerUp={() => {
              const travelled = drag
              startX.current = null
              if (Math.abs(travelled) >= SWIPE_THRESHOLD) void vote(travelled > 0)
              else setDrag(0)
            }}
            onPointerCancel={() => {
              startX.current = null
              setDrag(0)
            }}
          >
            {current.posterPath ? (
              <img src={posterUrl(current.posterPath, 'w342')} alt="" draggable={false} className="mx-auto w-48 rounded shadow" />
            ) : (
              <div className="mx-auto flex h-64 w-48 items-center justify-center rounded bg-muted text-sm text-muted-foreground">
                No poster
              </div>
            )}
            <h2 className="mt-3 text-center text-lg font-semibold">{current.title}</h2>
            {current.year ? <p className="text-center text-sm text-muted-foreground">{current.year}</p> : null}
            {/* Batch S7, `DECISIONS.md` #157's third point: **the card answers "what is
                this" before a swipe** — runtime, genres and top billing. */}
            {(current.runtimeMinutes ?? current.genres.length > 0) ? (
              <p className="mt-1 text-center text-xs text-muted-foreground">
                {[
                  current.runtimeMinutes
                    ? `${String(Math.floor(current.runtimeMinutes / 60))}h ${String(current.runtimeMinutes % 60)}m`
                    : null,
                  current.genres.join(' · ') || null,
                ]
                  .filter(Boolean)
                  .join(' · ')}
              </p>
            ) : null}
            {current.suggestedBy ? (
              <p className="mt-1 text-center text-xs text-primary">Suggested by {current.suggestedBy}</p>
            ) : null}
            {current.overview ? <p className="mt-2 line-clamp-4 text-sm text-muted-foreground">{current.overview}</p> : null}
            {current.cast.length > 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">Starring</span> {current.cast.join(', ')}
              </p>
            ) : null}
            {/* #157's fourth point: which of the *others* have seen it, and when. */}
            {current.watchedBy.length > 0 ? (
              <p className="mt-2 flex items-start gap-1.5 text-xs text-warning">
                <Eye className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                <span>{current.watchedBy.map((seen) => `${seen.personName} saw this on ${formatShortDate(seen.watchedAt)}`).join(' · ')}</span>
              </p>
            ) : null}
            {current.streamingOn.length > 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">Streaming on</span> {current.streamingOn.join(', ')}
              </p>
            ) : null}
            {filmPath(current) ? (
              <p className="mt-3 text-center">
                <Link to={filmPath(current) ?? '/movies'} className="text-xs font-semibold text-primary hover:underline" onClick={(event) => event.stopPropagation()}>
                  Open its full details
                </Link>
              </p>
            ) : null}
          </div>

          {/* Batch T4, snag 10e: **"Skip" and "Add", said in words.** A cross and a heart
              left the heart to be read as "favourite" rather than "yes, tonight". */}
          <div className="flex w-full items-center justify-between gap-3">
            <Button type="button" variant="outline" size="lg" className="flex-1" disabled={busy} onClick={() => void vote(false)}>
              <X className="h-5 w-5" aria-hidden /> Skip
            </Button>
            <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
              {index + 1} of {undecided.length}
            </span>
            <Button type="button" size="lg" className="flex-1" disabled={busy} onClick={() => void vote(true)}>
              <Check className="h-5 w-5" aria-hidden /> Add
            </Button>
          </div>
        </>
      )}

      {/* Batch S7, #157's first point: **anyone in the session can add to the list**. */}
      {open ? <SuggestFilmPanel sessionId={id} /> : null}

      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}
