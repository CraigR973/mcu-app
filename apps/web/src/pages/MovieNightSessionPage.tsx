import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, ChevronDown, Eye, Link2, Plus, Popcorn, Send } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import type {
  MovieNightCandidate,
  MovieNightCandidateList,
  MovieNightMatch,
  MovieNightSession,
} from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import { Poster } from '@/components/movies/Poster'
import { FeelingLucky } from '@/components/movies/FeelingLucky'
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
import { imdbUrl, letterboxdUrl } from '@/lib/external-links'
import { placeLabel } from '@/lib/place'
import { shareLink } from '@/lib/share'
import { cn, formatShortDate, formatDateTime } from '@/lib/utils'

/** "You and Mark", "You, Mark and Sam" — who is in tonight, from where you sit. */
function peopleLine(session: MovieNightSession, you: string | undefined): string {
  const others = session.people.filter((person) => person.id !== you).map((person) => person.displayName)
  if (others.length === 0) return 'Just you so far'
  if (others.length === 1) return `You and ${others[0]}`
  return `You, ${others.slice(0, -1).join(', ')} and ${others[others.length - 1]}`
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
 * The one control each film has — Batch V3, snag 4 (#228).
 *
 * "Add" puts your vote on it and "Added" takes the vote back. The API already replaces a
 * vote (`record_vote`), so taking one back is a vote of `false`, and the film reads "Add"
 * again. A match is still everyone adding the same film, announced once: the server marks
 * it announced, so taking a vote back and adding it again does not announce it twice.
 */
function AddToggle({
  card,
  pending,
  disabled,
  onToggle,
}: {
  card: MovieNightCandidate
  pending: boolean
  disabled: boolean
  onToggle: () => void
}) {
  const added = card.myVote === true
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={pending || disabled}
      aria-pressed={added}
      className={cn(
        'touch-target inline-flex min-h-9 shrink-0 items-center justify-center gap-1 rounded-full border px-3 text-xs font-semibold transition-colors disabled:opacity-60',
        added
          ? 'border-success/30 bg-success/12 text-success hover:bg-success/20'
          : 'border-input bg-background text-foreground hover:border-ring hover:bg-accent/15',
      )}
    >
      {added ? <Check className="h-3.5 w-3.5" aria-hidden /> : <Plus className="h-3.5 w-3.5" aria-hidden />}
      {added ? 'Added' : 'Add'}
      <span className="sr-only"> {card.title}</span>
    </button>
  )
}

/** What the swipe card used to say, opened in the row: "what is this, and have they seen it". */
function FilmDetails({ card }: { card: MovieNightCandidate }) {
  const runtime = card.runtimeMinutes
    ? `${String(Math.floor(card.runtimeMinutes / 60))}h ${String(card.runtimeMinutes % 60)}m`
    : null
  const facts = [runtime, card.genres.join(' · ') || null].filter(Boolean).join(' · ')
  const path = filmPath(card)
  const people = card.people ?? []
  const locations = card.locations ?? []
  const hasPlace = locations.some((place) => Boolean(place.location || place.section || place.shelf))
  const imdb = imdbUrl({ imdbId: card.imdbId ?? null })
  return (
    <div className="space-y-2 px-3 pb-3 text-sm">
      {facts ? <p className="text-xs text-muted-foreground">{facts}</p> : null}
      {card.overview ? <p className="text-muted-foreground">{card.overview}</p> : null}
      {card.cast.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Starring</span> {card.cast.join(', ')}
        </p>
      ) : null}
      {people.length > 0 ? (
        <ul className="space-y-1" aria-label="Watch history and personal ratings">
          {people.map((person) => (
            <li key={person.personId} className="text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">{person.personName}</span>: {person.lastWatchedAt ? `last watched ${formatShortDate(person.lastWatchedAt)}` : 'no watch logged'}
              {' · '}{person.personalRating === null ? 'not rated' : `${String(person.personalRating)}/5`}
            </li>
          ))}
        </ul>
      ) : null}
      {/* Older cached nights carry only the other participants' last watch. */}
      {people.length === 0 && card.watchedBy.length > 0 ? (
        <p className="flex items-start gap-1.5 text-xs text-warning">
          <Eye className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          <span>{card.watchedBy.map((seen) => `${seen.personName} saw this on ${formatShortDate(seen.watchedAt)}`).join(' · ')}</span>
        </p>
      ) : null}
      {locations.length > 0 ? (
        <div className="text-xs text-muted-foreground">
          <p className="font-semibold text-foreground">Our copies</p>
          <ul>{locations.map((place, index) => <li key={index}>{placeLabel(place)}</li>)}</ul>
        </div>
      ) : null}
      {!hasPlace && card.streamingOn.length > 0 ? (
        <p className="text-xs text-muted-foreground">
          <span className="font-semibold text-foreground">Streaming on</span> {card.streamingOn.join(', ')}{' '}
          {card.streamingLink ? <a href={card.streamingLink} target="_blank" rel="noreferrer" className="underline">JustWatch via TMDB</a> : <span className="opacity-80">(JustWatch)</span>}
        </p>
      ) : null}
      {!hasPlace && card.streamingOn.length === 0 ? <p className="text-xs text-muted-foreground">No recorded location or streaming service found.</p> : null}
      {!card.runtimeMinutes ? <p className="text-xs text-muted-foreground">Runtime unavailable.</p> : null}
      <p className="text-xs text-muted-foreground">
        {imdb ? <a href={imdb} target="_blank" rel="noreferrer" className="font-semibold text-primary underline">IMDb</a> : 'IMDb'}: {card.imdbRating == null ? (card.imdbCheckedAt ? 'not rated' : 'score unavailable') : `${String(card.imdbRating)}/10`}
        {card.imdbVotes != null ? ` · ${String(card.imdbVotes)} votes` : ''}
        {card.imdbCheckedAt ? ` · checked ${formatShortDate(card.imdbCheckedAt)}` : ''}
      </p>
      <div className="flex flex-wrap items-center gap-4">
        <a href={letterboxdUrl({ title: card.title, imdbId: card.imdbId ?? null })} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center text-xs font-semibold text-primary underline">Letterboxd</a>
        {path ? (
          <Link to={path} className="inline-flex min-h-11 items-center text-xs font-semibold text-primary hover:underline">
            Open its page
          </Link>
        ) : null}
      </div>
    </div>
  )
}

/**
 * Tonight's shortlist, the whole of a night — Batch T4, snag 10b; since Batch V3 the only
 * screen (#228).
 *
 * **Each film has one Add / Added control, and tapping the film opens its details in the
 * row.** Choosing a film means comparing films, and only a list shows them side by side;
 * the swipe deck that sat behind "Start swiping" is gone, with its gestures, its arrow keys
 * and its "N of M" count. Your own vote is shown on each film; **the other person's never
 * is** (#157) — seeing their answer first changes the game.
 */
function Shortlist({
  cards,
  title,
  headingId,
  pendingId,
  readOnly,
  onToggle,
}: {
  cards: MovieNightCandidate[]
  title: string
  headingId: string
  pendingId: string | null
  readOnly: boolean
  onToggle: (card: MovieNightCandidate) => void
}) {
  const [opened, setOpened] = useState<ReadonlySet<string>>(() => new Set())
  const added = cards.filter((card) => card.myVote === true).length

  function toggleOpen(suggestionId: string) {
    setOpened((current) => {
      const next = new Set(current)
      if (next.has(suggestionId)) next.delete(suggestionId)
      else next.add(suggestionId)
      return next
    })
  }

  return (
    <section className="space-y-3" aria-labelledby={headingId}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id={headingId} className="section-heading text-base">
          {title} <span className="font-sans text-sm font-normal text-muted-foreground">· {cards.length} {cards.length === 1 ? 'film' : 'films'}</span>
        </h2>
        <p className="text-sm text-muted-foreground">
          {added === 0 ? 'Add the ones you would watch tonight.' : `You've added ${String(added)}.`}
        </p>
      </div>
      <ul className="archive-panel divide-y divide-border overflow-hidden">
        {cards.map((card) => {
          const open = opened.has(card.suggestionId)
          const detailsId = `film-details-${card.suggestionId}`
          return (
            <li key={card.suggestionId}>
              <div className="flex min-h-16 items-center gap-2 px-3 py-2">
                <button
                  type="button"
                  onClick={() => toggleOpen(card.suggestionId)}
                  aria-expanded={open}
                  aria-controls={detailsId}
                  className="flex min-w-0 flex-1 items-center gap-3 rounded-md text-left hover:bg-muted/40"
                >
                  <Poster path={card.posterPath} title={card.title} size="w92" decorative className="h-16 w-11 shrink-0 rounded-sm" />
                  <span className="min-w-0 flex-1">
                    <span className="flex min-w-0 items-baseline gap-2">
                      <span className="truncate text-sm font-semibold text-foreground">{card.title}</span>
                      {card.year ? <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{card.year}</span> : null}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {card.suggestedBy ? `Suggested by ${card.suggestedBy}${card.suggestedAt ? ` · ${formatDateTime(card.suggestedAt)}` : ''}` : 'From the Archive'}
                      {card.movieId ? '' : card.streamingOn.length > 0 ? ` · on ${card.streamingOn.join(', ')}` : ' · not on the shelf'}
                    </span>
                  </span>
                  <ChevronDown
                    className={cn('h-4 w-4 shrink-0 text-muted-foreground transition-transform', open && 'rotate-180')}
                    aria-hidden
                  />
                </button>
                <AddToggle
                  card={card}
                  pending={pendingId === card.suggestionId}
                  disabled={readOnly}
                  onToggle={() => onToggle(card)}
                />
              </div>
              <div id={detailsId} hidden={!open}>
                {open ? <FilmDetails card={card} /> : null}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

/**
 * §8.4 — a movie night: the shortlist, and sending it to the other person.
 *
 * **One screen since Batch V3** (#228): Craig chose the list over the swipe deck, which
 * retires Phase 8.4's "swipe-like UI" and #207's arrow-key rule. Everything the deck's card
 * said is in the row, a tap away.
 *
 * **The other person's votes are never shown.** The event stream says only that *a* vote
 * happened, and the list shows each person their own votes alone.
 */
export default function MovieNightSessionPage() {
  const { id = '' } = useParams()
  const { profile } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [match, setMatch] = useState<MovieNightMatch | null>(null)
  // "Keep going" hides the match the session remembers, until a new one arrives.
  const [dismissedStored, setDismissedStored] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [realtimeError, setRealtimeError] = useState<string | null>(null)

  const session = useQuery({
    queryKey: ['movie-night', id],
    queryFn: () => fetchMovieNight(id),
    enabled: Boolean(id),
  })
  const shortlist = useQuery({
    queryKey: ['movie-night-candidates', id],
    queryFn: () => fetchMovieNightCandidates(id),
    enabled: Boolean(id),
  })

  // §8.4's realtime half. A match found by the *other* person's vote arrives here, and
  // since Batch T4 so does a film they suggest, so the list is the same on both phones.
  useEffect(() => {
    if (!id) return
    let cancelled = false
    void (async () => {
      try {
        for await (const event of streamMovieNightEvents(id)) {
          if (cancelled) return
          setRealtimeError(null)
          if (event.kind === 'match' && event.title) {
            setMatch({
              movieId: event.movieId ?? null,
              title: event.title,
              year: event.year ?? null,
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

  const vote = useMutation({
    mutationFn: ({ card, liked }: { card: MovieNightCandidate; liked: boolean }) =>
      castMovieNightVote(id, card.suggestionId, liked),
    onMutate: () => setError(null),
    onSuccess: (result, { card, liked }) => {
      // Only your own vote changes on screen, so the list is updated in place rather than
      // re-read: a re-read would show nothing new, and the other person's votes never come.
      queryClient.setQueryData<MovieNightCandidateList>(['movie-night-candidates', id], (list) =>
        list
          ? {
              ...list,
              items: list.items.map((item) =>
                item.suggestionId === card.suggestionId ? { ...item, myVote: liked } : item,
              ),
            }
          : list,
      )
      if (result.match) setMatch(result.match)
    },
    onError: (cause) => setError(queryErrorMessage(cause, 'That vote did not register.')),
  })

  // A match just made on this screen, else the one the session remembers (Batch X12a), so a
  // night opened from the "It's a match" push shows its match.
  const shownMatch = match ?? (dismissedStored ? null : (session.data?.match ?? null))
  const cards = shortlist.data?.items ?? []
  const shortlistState = listState(shortlist, cards.length === 0)

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
            {peopleLine(night, profile?.id)} · {night.plannedStart ? `Planned ${formatDateTime(night.plannedStart)}` : formatShortDate(night.createdAt)}
            {night.status === 'ended' ? ' · this one has ended' : ''}
          </p>
        ) : null}
      </header>

      {open ? <SuggestFilmPanel sessionId={id} /> : null}

      {open ? <FeelingLucky sessionId={id} /> : null}

      {night && open ? <InviteBar session={night} you={profile?.id} /> : null}

      {realtimeError ? (
        <p role="status" className="w-full rounded-md border border-warning/45 bg-warning/10 p-3 text-sm text-foreground">
          {realtimeError}
        </p>
      ) : null}

      {shownMatch ? (
        <div role="status" className="w-full rounded-lg border-2 border-success bg-success/10 p-6 text-center">
          <Check className="mx-auto h-8 w-8 text-success" aria-hidden />
          <p className="mt-2 text-lg font-bold">It's a match</p>
          <p className="mt-1 text-xl">
            {shownMatch.title}
            {shownMatch.year ? ` (${String(shownMatch.year)})` : ''}
          </p>
          {shownMatch.posterPath ? (
            <img src={posterUrl(shownMatch.posterPath)} alt="" className="mx-auto mt-3 w-32 rounded shadow" />
          ) : null}
          <div className="mt-4 flex justify-center gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setMatch(null)
                setDismissedStored(true)
              }}
            >
              Keep going
            </Button>
            <Button onClick={() => navigate('/movie-night')}>Done</Button>
          </div>
        </div>
      ) : shortlistState === 'loading' ? (
        <StatePanel className="w-full" tone="loading" title="Preparing the shortlist" />
      ) : shortlistState === 'offline' ? (
        <StatePanel className="w-full" tone="offline" title="The shortlist needs the network" description="Reconnect to load the films in this screening." />
      ) : shortlistState === 'error' ? (
        <StatePanel
          className="w-full"
          tone="error"
          title="Shortlist unavailable"
          description={queryErrorMessage(shortlist.error, 'The films for this screening could not be loaded.')}
        />
      ) : shortlistState === 'empty' ? (
        <StatePanel
          className="w-full"
          tone="empty"
          title="No films on the list yet"
          description="Suggest one above, or start another night with a wider year range."
        />
      ) : (
        <>
          <Shortlist
            title="Suggested"
            headingId="suggested-heading"
            cards={cards.filter((card) => card.suggestedBy !== null)}
            pendingId={vote.isPending ? (vote.variables?.card.suggestionId ?? null) : null}
            readOnly={night?.status === 'ended'}
            onToggle={(card) => vote.mutate({ card, liked: card.myVote !== true })}
          />
          <Shortlist
            title="Stuck for ideas? A random shortlist"
            headingId="archive-heading"
            cards={cards.filter((card) => card.suggestedBy === null)}
            pendingId={vote.isPending ? (vote.variables?.card.suggestionId ?? null) : null}
            readOnly={night?.status === 'ended'}
            onToggle={(card) => vote.mutate({ card, liked: card.myVote !== true })}
          />
        </>
      )}

      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
      <p className="text-xs text-muted-foreground">Information courtesy of <a href="https://www.imdb.com" target="_blank" rel="noreferrer" className="underline">IMDb</a>. Used with permission.</p>
    </div>
  )
}
