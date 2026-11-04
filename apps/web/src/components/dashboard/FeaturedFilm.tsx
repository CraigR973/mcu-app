import { Shuffle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Poster } from '@/components/movies/Poster'
import { Button } from '@/components/ui/button'
import type { FeaturedPick } from '@/lib/home-films'
import { useLuckyDeck } from '@/lib/lucky-deck'
import { queryErrorMessage } from '@/lib/query-state'
import { cn, formatShortDate } from '@/lib/utils'

const BUTTON = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold'

/**
 * Home's one featured film, with Feeling lucky inside it — AC2, Craig's pick (#337).
 *
 * It opens on the first of the person's "Worth a rewatch" films, or the most rewatched when they
 * have none, both already read for Home's rows, so it costs no request. "Deal another" is
 * AA6's deal: one film at a time from the Archive, never the same twice in a run, with the
 * unwatched-only switch. Opening the film is the choice; it logs no watch.
 *
 * AB7's guard stays: the deal and the switch take no tap while Home's first layout arrives.
 */
export function FeaturedFilm({ pick, homeLayoutPending = false }: { pick: FeaturedPick | null; homeLayoutPending?: boolean }) {
  const deck = useLuckyDeck({ alsoExclude: pick ? [pick.movieId] : [] })
  const { film, draw, exhausted, started } = deck
  const busy = draw.isPending || homeLayoutPending

  const shown = film
    ? {
        movieId: film.id,
        title: film.title,
        posterPath: film.posterPath,
        eyebrow: 'From the Archive',
        detail: [
          [film.year, film.runtimeMinutes ? `${String(film.runtimeMinutes)} min` : null].filter(Boolean).join(' · '),
          film.lastWatchedAt ? `Last watched ${formatShortDate(film.lastWatchedAt)}` : 'No watch logged by you',
          film.locations.map((place) => place.label).join(' · '),
        ].filter(Boolean).join('. '),
      }
    : pick

  return (
    <section aria-labelledby="home-featured-title" className="archive-panel flex gap-4 p-4">
      {shown ? (
        <Poster key={shown.movieId} path={shown.posterPath} title={shown.title} decorative className="w-28 shrink-0 self-start rounded-md border border-border" />
      ) : (
        <div aria-hidden className="flex aspect-[2/3] w-28 shrink-0 items-center justify-center self-start rounded-md border border-dashed border-border text-muted-foreground">
          <Shuffle className="size-6" />
        </div>
      )}
      <div className="min-w-0 flex-1" aria-live="polite" aria-busy={draw.isPending}>
        <p className="metadata-label">{exhausted ? 'Feeling lucky' : shown?.eyebrow ?? 'Feeling lucky'}</p>
        <h2 id="home-featured-title" className="mt-1 font-display text-xl font-semibold leading-tight text-foreground">
          {exhausted ? 'That was the whole run' : shown?.title ?? 'Let the Archive choose'}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {exhausted
            ? 'No more films for this run. Start again to deal a fresh run.'
            : shown?.detail ?? 'One film at a time from the Archive. Skip until one feels right.'}
        </p>
        <div role="group" aria-label="Feeling lucky" aria-busy={homeLayoutPending} className="mt-3 space-y-1">
          <div className="flex flex-wrap gap-2">
            {shown && !exhausted ? (
              <Link to={`/movies/${shown.movieId}`} className={cn(BUTTON, 'bg-primary text-primary-foreground hover:bg-primary/90')}>
                Open the film
              </Link>
            ) : null}
            {!exhausted ? (
              <Button type="button" variant="outline" disabled={busy} onClick={deck.deal} className="min-h-11">
                <Shuffle className="size-4" aria-hidden />
                {draw.isPending ? 'Dealing…' : draw.isError ? 'Try again' : shown ? 'Deal another' : 'Deal a film'}
              </Button>
            ) : null}
            {started ? (
              <Button type="button" variant="ghost" disabled={busy} onClick={deck.reset} className="min-h-11">
                Start again
              </Button>
            ) : null}
          </div>
          <label className="flex min-h-11 cursor-pointer items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={deck.unwatchedOnly}
              disabled={started || homeLayoutPending}
              onChange={(event) => deck.setUnwatchedOnly(event.target.checked)}
              className="h-4 w-4 accent-primary"
            />
            Only films I haven’t watched
          </label>
          {homeLayoutPending ? <p role="status" className="text-xs text-muted-foreground">Loading Home…</p> : null}
          {draw.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(draw.error, 'Could not deal a film. Try again.')}</p> : null}
        </div>
      </div>
    </section>
  )
}
