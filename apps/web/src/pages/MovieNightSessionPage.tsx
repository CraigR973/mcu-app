import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Heart, Loader2, Popcorn, X } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import type { MovieNightCandidate, MovieNightMatch } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import {
  castMovieNightVote,
  fetchMovieNight,
  fetchMovieNightCandidates,
  posterUrl,
  streamMovieNightEvents,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/** How far a card must travel before it counts as a swipe rather than a wobble. */
const SWIPE_THRESHOLD = 90

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
      for await (const event of streamMovieNightEvents(id)) {
        if (cancelled) return
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
    })()
    return () => {
      cancelled = true
    }
  }, [id, queryClient])

  const cards = deck.data?.items ?? []
  const current: MovieNightCandidate | undefined = cards[index]

  const vote = useCallback(
    async (liked: boolean) => {
      if (!current || busy) return
      setBusy(true)
      setError(null)
      setDrag(0)
      try {
        const result = await castMovieNightVote(id, current.movieId, liked)
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
      if (match) return
      if (event.key === 'ArrowRight') void vote(true)
      if (event.key === 'ArrowLeft') void vote(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [match, vote])

  if (session.isError) {
    return (
      <p className="p-8 text-center text-sm text-destructive">
        {queryErrorMessage(session.error, 'That movie night could not be loaded.')}
      </p>
    )
  }

  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 p-4">
      <header className="w-full text-center">
        <h1 className="flex items-center justify-center gap-2 text-lg font-semibold">
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

      {match ? (
        <div className="w-full rounded-lg border-2 border-emerald-500 bg-emerald-500/10 p-6 text-center">
          <Check className="mx-auto h-8 w-8 text-emerald-600" aria-hidden />
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
            <Link to="/movie-night">
              <Button>Done</Button>
            </Link>
          </div>
        </div>
      ) : deck.isPending ? (
        <Loader2 className="mt-12 h-6 w-6 animate-spin text-muted-foreground" aria-hidden />
      ) : !current ? (
        <p className="mt-12 text-center text-sm text-muted-foreground">
          {cards.length === 0
            ? 'Nothing left to swipe on with these filters.'
            : 'That is the whole deck. No match yet — start another one, or loosen the filters.'}
        </p>
      ) : (
        <>
          <div
            role="group"
            aria-label={`${current.title}. Swipe right to like, left to pass.`}
            className={cn(
              'w-full select-none rounded-xl border border-border bg-card p-4 shadow-lg',
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
            {current.overview ? (
              <p className="mt-2 line-clamp-4 text-sm text-muted-foreground">
                {current.overview}
              </p>
            ) : null}
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
              {index + 1} of {cards.length}
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

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}
