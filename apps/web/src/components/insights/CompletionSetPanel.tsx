import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Bookmark, Check, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  addManyWanted,
  completionCountLabel,
  fetchCompletionSet,
  posterUrl,
  setTypeLabel,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'
import { useAuth } from '@/context/auth'

interface Props {
  setId: string
  onBack: () => void
  /** Where the back control goes, in words: Home since W2, the list of sets otherwise. */
  backLabel?: string
}

/**
 * §11.2's "bulk add missing to wanted list".
 *
 * Sequential, and it does not stop at the first refusal: a film already on the list
 * answers 409, which is a success from the reader's point of view, and one bad entry in a
 * set of forty should not abandon the other thirty-nine. The result says what actually
 * happened rather than claiming a round number.
 */
function BulkAddMissing({ tmdbIds }: { tmdbIds: number[] }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)

  const add = useMutation({
    mutationFn: () => addManyWanted(tmdbIds),
    onSuccess: () => {
      setConfirming(false)
      void queryClient.invalidateQueries({ queryKey: ['wanted'] })
      void queryClient.invalidateQueries({ queryKey: ['recommendations'] })
    },
  })

  if (tmdbIds.length === 0) return null

  return (
    <div className="space-y-2">
      {confirming ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" size="sm" disabled={add.isPending} onClick={() => add.mutate()}>
            {add.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Add all {tmdbIds.length}
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
          <span className="text-xs text-muted-foreground">
            Each is fetched from TMDB, so this takes a moment.
          </span>
        </div>
      ) : (
        <Button type="button" size="sm" variant="outline" onClick={() => setConfirming(true)}>
          <Bookmark className="h-4 w-4" />
          Add {tmdbIds.length} missing to wanted
        </Button>
      )}
      {add.data ? (
        <p className="text-xs text-muted-foreground">
          Added {add.data.added}
          {add.data.alreadyThere > 0 ? `, ${add.data.alreadyThere} already there` : ''}
          {add.data.failed > 0 ? `, ${add.data.failed} could not be added` : ''}.
        </p>
      ) : null}
      {add.isError ? <p role="alert" className="text-xs text-destructive">{queryErrorMessage(add.error, 'The missing films could not be added to Wanted.')}</p> : null}
    </div>
  )
}

/**
 * One set's films — §11.2's "missing films list with posters".
 *
 * Owned films link to their detail page; missing ones do not, because there is nothing to
 * link to. That is the whole distinction the page exists to draw, so it is drawn with a
 * tick and a dimmed poster rather than with a colour alone.
 *
 * **The "add missing to wanted list" button is §11.2's, and Batch 13 dropped it.** There
 * was no `wanted_list` table then, so the button would have done nothing — the defect
 * `STATUS.md` gotcha 5 catalogues. Batch 18 built §3.5, so it is here now, doing what it
 * says.
 */
export function CompletionSetPanel({ setId, onBack, backLabel = 'All sets' }: Props) {
  const { profile } = useAuth()
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
        {backLabel}
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
            <div role="progressbar" aria-label={`${set.setName} completion`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={set.percentComplete} className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  'h-full rounded-full',
                  set.percentComplete === 100 ? 'bg-primary' : 'bg-warning',
                )}
                style={{ width: `${String(set.percentComplete)}%` }}
              />
            </div>
          </div>

          {profile?.role === 'admin' ? <BulkAddMissing tmdbIds={set.films.filter((film) => !film.owned).map((film) => film.tmdbId)} /> : null}

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
                      <span className="absolute right-1 top-1 rounded-full bg-primary p-1 text-primary-foreground" aria-label="Owned">
                        <Check className="h-3 w-3" aria-hidden />
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
