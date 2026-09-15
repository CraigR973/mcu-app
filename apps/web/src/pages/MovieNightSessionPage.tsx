import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Eye, Heart, Popcorn, X } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import type { MovieNightCandidate, MovieNightMatch } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import { SuggestFilmPanel } from '@/components/movies/SuggestFilmPanel'
import {
  castMovieNightVote,
  fetchMovieNight,
  fetchMovieNightCandidates,
  posterUrl,
  streamMovieNightEvents,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

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

/**
 * §8.4 — the swipe deck.
 *
 * **The other person's votes are never shown.** The event stream says only that *a* vote
 * happened, and the deck is filtered by this person's own votes — a card vanishing because
 * they swiped it would leak which way they went, and a movie night where you can see the
 * other answer first is a different game.
 *
 * Gestures are pointer events rather than a drag library: one dependency avoided, and
 * pointer events cover mouse, touch and pen in one API. Keyboard works too, because a
 * gesture-only control is one nobody can use on a laptop.
 */
export default function MovieNightSessionPage() {
  const { id = '' } = useParams()
  const queryClient = useQueryClient()
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

  // §8.4's realtime half. A match found by the *other* person's swipe arrives here —
  // this person may already have voted and be looking at a later card.
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
  // **Batch S7: the list is shared, so it keeps what you have already voted on** — a
  // shortlist everyone is adding to is a list you re-read. The *swiping* still starts at
  // the first film you have not decided on, which is where Batch 35's deck left you.
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

  // Keyboard, because a gesture-only control cannot be used on a laptop.
  useEffect(() => {
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
  }, [busy, current, match, vote])

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

  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 px-4 pb-24 pt-6 sm:px-6">
      <header className="w-full border-b border-border pb-4 text-center">
        <p className="page-kicker">Screening room</p>
        <h1 className="flex items-center justify-center gap-2 font-display text-2xl font-semibold">
          <Popcorn className="h-5 w-5" aria-hidden />
          Movie night
        </h1>
        {session.data ? (
          <p className="text-xs text-muted-foreground">
            {session.data.participantCount === 1
              ? 'Waiting for somebody to join — share the invite from the list.'
              : `${session.data.participantCount} swiping`}
            {session.data.status === 'ended' ? ' · this one has ended' : ''}
          </p>
        ) : null}
      </header>

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
            <img
              src={posterUrl(match.posterPath)}
              alt=""
              className="mx-auto mt-3 w-32 rounded shadow"
            />
          ) : null}
          <div className="mt-4 flex justify-center gap-2">
            <Button variant="outline" onClick={() => setMatch(null)}>
              Keep swiping
            </Button>
            <Button asChild>
              <Link to="/movie-night">Done</Link>
            </Button>
          </div>
        </div>
      ) : deckState === 'loading' ? (
        <StatePanel className="w-full" tone="loading" title="Preparing the shortlist" />
      ) : deckState === 'offline' ? (
        <StatePanel
          className="w-full"
          tone="offline"
          title="The shortlist needs the network"
          description="Reconnect to load the films in this screening."
        />
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
          title="No films match this screening"
          description="Start another screening with a wider year range."
          action={(
            <Button asChild variant="outline">
              <Link to="/movie-night">Back to movie night</Link>
            </Button>
          )}
        />
      ) : !current ? (
        <StatePanel
          className="w-full"
          tone="empty"
          title="That is the whole deck"
          description="There is no match yet. Start another screening or loosen the filters."
          action={(
            <Button asChild variant="outline">
              <Link to="/movie-night">Start another</Link>
            </Button>
          )}
        />
      ) : (
        <>
          <div
            role="group"
            aria-label={`${current.title}. Swipe right to like, left to pass.`}
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
              <img
                src={posterUrl(current.posterPath, 'w342')}
                alt=""
                draggable={false}
                className="mx-auto w-48 rounded shadow"
              />
            ) : (
              <div className="mx-auto flex h-64 w-48 items-center justify-center rounded bg-muted text-sm text-muted-foreground">
                No poster
              </div>
            )}
            <h2 className="mt-3 text-center text-lg font-semibold">{current.title}</h2>
            {current.year ? (
              <p className="text-center text-sm text-muted-foreground">{current.year}</p>
            ) : null}
            {/* Batch S7, `DECISIONS.md` #157's third point: **the card answers "what is
                this" before a swipe** — runtime, genres and top billing, so nobody has to
                open another screen to decide. */}
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
              <p className="mt-1 text-center text-xs text-primary">
                Suggested by {current.suggestedBy}
              </p>
            ) : null}

            {current.overview ? (
              <p className="mt-2 line-clamp-4 text-sm text-muted-foreground">
                {current.overview}
              </p>
            ) : null}

            {current.cast.length > 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">Starring</span>{' '}
                {current.cast.join(', ')}
              </p>
            ) : null}

            {/* #157's fourth point. **Empty until the S8 import runs** — `watch_log` held
                0 rows when this shipped, which is why S7 follows S8 in the order. */}
            {current.watchedBy.length > 0 ? (
              <p className="mt-2 flex items-start gap-1.5 text-xs text-warning">
                <Eye className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                <span>
                  {current.watchedBy
                    .map((seen) => `${seen.personName} saw this on ${seen.watchedAt}`)
                    .join(' · ')}
                </span>
              </p>
            ) : null}

            {/* A film nobody owns still has to be watchable somewhere, or suggesting it
                is a dead end. `get_watch_providers` already existed (#157). */}
            {current.streamingOn.length > 0 ? (
              <p className="mt-2 text-xs text-muted-foreground">
                <span className="font-semibold text-foreground">Streaming on</span>{' '}
                {current.streamingOn.join(', ')}
              </p>
            ) : null}

            {current.movieId ? (
              <p className="mt-3 text-center">
                <Link
                  to={`/movies/${current.movieId}`}
                  className="text-xs font-semibold text-primary hover:underline"
                  onClick={(event) => event.stopPropagation()}
                >
                  Open its full details
                </Link>
              </p>
            ) : (
              <p className="mt-3 text-center text-xs text-muted-foreground">
                Not in the collection — this one would be a rental.
              </p>
            )}
          </div>

          <div className="flex items-center gap-6">
            <Button
              size="icon"
              variant="outline"
              aria-label="Pass"
              disabled={busy}
              onClick={() => void vote(false)}
            >
              <X className="h-5 w-5" aria-hidden />
            </Button>
            <span className="text-xs text-muted-foreground">
              {index + 1} of {undecided.length}
            </span>
            <Button
              size="icon"
              aria-label="Like"
              disabled={busy}
              onClick={() => void vote(true)}
            >
              <Heart className="h-5 w-5" aria-hidden />
            </Button>
          </div>
        </>
      )}

      {/* Batch S7, #157's first point: **anyone in the session can add to the list**,
          and the list is the same for everybody. Below the deck rather than above it —
          the common act is swiping, and adding is the occasional one. */}
      {session.data?.status === 'open' ? <SuggestFilmPanel sessionId={id} /> : null}

      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}
