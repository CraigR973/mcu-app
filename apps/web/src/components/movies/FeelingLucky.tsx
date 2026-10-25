import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Shuffle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/context/auth'
import { Button } from '@/components/ui/button'
import { Poster } from '@/components/movies/Poster'
import { dealLuckyFilm, suggestMovieNightFilm, type MovieListItem } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { formatShortDate } from '@/lib/utils'

/** An account or night change ends the old browser run, including outstanding results. */
export function FeelingLucky({ sessionId }: { sessionId?: string }) {
  const { profile } = useAuth()
  if (!profile) return null
  return <LuckyRun key={`${profile.id}:${sessionId ?? 'home'}`} sessionId={sessionId} />
}

function LuckyRun({ sessionId }: { sessionId?: string }) {
  const queryClient = useQueryClient()
  const [unwatchedOnly, setUnwatchedOnly] = useState(false)
  const [started, setStarted] = useState(false)
  const [seen, setSeen] = useState<string[]>([])
  const [film, setFilm] = useState<MovieListItem | null>(null)
  const [exhausted, setExhausted] = useState(false)
  const [chosen, setChosen] = useState<MovieListItem | null>(null)

  const draw = useMutation({
    mutationFn: (excludedIds: string[]) => dealLuckyFilm({ excludedIds, unwatchedOnly, sessionId }),
    onSuccess: ({ film: next }) => {
      setFilm(next)
      setExhausted(next === null)
      if (next) setSeen((ids) => [...ids, next.id])
    },
  })
  const take = useMutation({
    mutationFn: async (pick: MovieListItem) => {
      if (sessionId) await suggestMovieNightFilm(sessionId, { movieId: pick.id })
      return pick
    },
    onSuccess: (pick) => {
      setChosen(pick)
      if (sessionId) void queryClient.invalidateQueries({ queryKey: ['movie-night-candidates', sessionId] })
    },
  })
  const busy = draw.isPending || take.isPending
  const deal = () => {
    setStarted(true)
    take.reset()
    draw.mutate(seen)
  }
  const reset = () => {
    setStarted(false)
    setSeen([])
    setFilm(null)
    setExhausted(false)
    setChosen(null)
    draw.reset()
    take.reset()
  }

  return (
    <fieldset className="min-w-0 space-y-3 rounded-xl border border-border bg-card p-4">
      <legend className="section-heading inline-flex items-center gap-2 px-1 text-base">
        <Shuffle className="h-4 w-4" aria-hidden /> Feeling lucky
      </legend>
      <p className="text-xs text-muted-foreground">
        One film at a time from the Archive. Skip until one feels right.
      </p>
      {!sessionId ? (
        <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={unwatchedOnly}
            disabled={started}
            onChange={(event) => setUnwatchedOnly(event.target.checked)}
            className="h-4 w-4 accent-primary"
          />
          Only films I haven’t watched
        </label>
      ) : null}

      {chosen ? (
        <div className="space-y-2">
          <p role="status" className="text-sm text-success">
            <Check className="mr-1 inline h-4 w-4" aria-hidden />
            {sessionId ? `Added “${chosen.title}” to tonight’s suggestions.` : `Your pick: ${chosen.title}.`}
          </p>
          {!sessionId ? <Link className="inline-flex min-h-11 items-center text-sm font-semibold text-primary underline" to={`/movies/${chosen.id}`}>Open film</Link> : null}
        </div>
      ) : (
        <>
          <div aria-live="polite" aria-busy={draw.isPending}>
            {film ? (
              <div className="flex gap-3">
                <Poster key={film.id} path={film.posterPath} title={film.title} decorative className="w-20 shrink-0 self-start rounded" />
                <div className="min-w-0 space-y-1">
                  <h3 className="font-display text-lg font-semibold">{film.title}</h3>
                  <p className="text-xs text-muted-foreground">
                    {[film.year, film.runtimeMinutes ? `${String(film.runtimeMinutes)} min` : null].filter(Boolean).join(' · ')}
                  </p>
                  <p className="text-xs text-muted-foreground">{film.lastWatchedAt ? `Last watched ${formatShortDate(film.lastWatchedAt)}` : 'No watch logged by you'}</p>
                  {film.locations.length ? <p className="text-xs text-muted-foreground">{film.locations.map((place) => place.label).join(' · ')}</p> : null}
                  <Link className="inline-flex min-h-11 items-center text-sm text-primary underline" to={`/movies/${film.id}`}>Film details</Link>
                </div>
              </div>
            ) : exhausted ? (
              <p className="text-sm text-muted-foreground">No more films for this run. Start again to deal a fresh run.</p>
            ) : draw.isPending ? (
              <p className="text-sm text-muted-foreground">Dealing a film…</p>
            ) : null}
          </div>
          {!exhausted ? (
            <div className="flex flex-wrap gap-2">
              {film ? <Button type="button" disabled={busy} onClick={() => take.mutate(film)}>{take.isPending ? 'Choosing…' : 'Choose this film'}</Button> : null}
              <Button type="button" variant="outline" disabled={busy} onClick={deal}>
                {draw.isPending ? 'Dealing…' : draw.isError ? 'Try again' : film ? 'Skip this film' : 'Deal a film'}
              </Button>
            </div>
          ) : null}
        </>
      )}

      {draw.isError && !chosen ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(draw.error, 'Could not deal a film. Try again.')}</p> : null}
      {take.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(take.error, 'That film could not be chosen. Try again or skip it.')}</p> : null}
      {started ? <Button type="button" variant="ghost" disabled={busy} onClick={reset}>Start again</Button> : null}
    </fieldset>
  )
}
