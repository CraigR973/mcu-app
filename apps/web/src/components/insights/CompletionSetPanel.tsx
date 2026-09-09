import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Check } from 'lucide-react'
import { Link } from 'react-router-dom'

import { completionCountLabel, fetchCompletionSet, posterUrl, setTypeLabel } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

interface Props {
  setId: string
  onBack: () => void
}

/**
 * One set's films — §11.2's "missing films list with posters".
 *
 * Owned films link to their detail page; missing ones do not, because there is nothing to
 * link to. That is the whole distinction the page exists to draw, so it is drawn with a
 * tick and a dimmed poster rather than with a colour alone.
 */
export function CompletionSetPanel({ setId, onBack }: Props) {
  const setQuery = useQuery({
    queryKey: ['completion-set', setId],
    queryFn: () => fetchCompletionSet(setId),
  })
  const set = setQuery.data

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-8">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        All sets
      </button>

      {setQuery.isError ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(setQuery.error, 'Could not load this set.')}
        </p>
      ) : !set ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <>
          <div>
            <h1 className="text-2xl font-bold text-foreground">{set.setName}</h1>
            <p className="text-sm text-muted-foreground">
              {setTypeLabel(set.setType)} · {completionCountLabel(set)} ·{' '}
              {set.percentComplete}% complete
            </p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  'h-full rounded-full',
                  set.percentComplete === 100 ? 'bg-primary' : 'bg-amber-500',
                )}
                style={{ width: `${String(set.percentComplete)}%` }}
              />
            </div>
          </div>

          <ul className="grid grid-cols-3 gap-3 sm:grid-cols-4 md:grid-cols-6">
            {set.films.map((film) => {
              const card = (
                <div className="space-y-1">
                  <div className="relative">
                    <img
                      src={posterUrl(film.posterPath, 'w185')}
                      alt=""
                      loading="lazy"
                      className={cn(
                        'aspect-[2/3] w-full rounded object-cover',
                        film.owned ? '' : 'opacity-40 grayscale',
                      )}
                    />
                    {film.owned ? (
                      <span className="absolute right-1 top-1 rounded-full bg-primary p-0.5 text-primary-foreground">
                        <Check className="h-3 w-3" />
                      </span>
                    ) : null}
                  </div>
                  <p
                    className={cn(
                      'truncate text-xs',
                      film.owned ? 'text-foreground' : 'text-muted-foreground',
                    )}
                    title={film.title}
                  >
                    {film.title}
                  </p>
                  <p className="text-[11px] text-muted-foreground">{film.year ?? '—'}</p>
                </div>
              )
              return (
                <li key={film.tmdbId}>
                  {film.movieId ? <Link to={`/movies/${film.movieId}`}>{card}</Link> : card}
                </li>
              )
            })}
          </ul>
        </>
      )}
    </div>
  )
}
