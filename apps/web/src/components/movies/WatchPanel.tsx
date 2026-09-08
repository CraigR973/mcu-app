import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, Loader2, Star, Trash2 } from 'lucide-react'

import { deleteWatch, fetchWatches, logWatch, RATING_STEPS } from '@/lib/api'

interface Props {
  movieId: string
}

function formatWatchedAt(value: string): string {
  // `watchedAt` is a plain YYYY-MM-DD. Parsing it with `new Date()` would read it as
  // UTC midnight and render the day before for anyone west of Greenwich, so the parts
  // are used directly.
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return value
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function Stars({
  value,
  onChange,
}: {
  value: number | null
  onChange: (rating: number | null) => void
}) {
  return (
    <div className="flex items-center gap-0.5" role="group" aria-label="Your rating">
      {RATING_STEPS.filter((step) => Number.isInteger(step)).map((step) => (
        <button
          key={step}
          type="button"
          // Clicking the star you already chose clears the rating — otherwise a
          // rating given by accident can only be changed, never removed.
          onClick={() => onChange(value === step ? null : step)}
          aria-label={`${step} star${step === 1 ? '' : 's'}`}
          aria-pressed={value != null && value >= step}
          className="p-0.5"
        >
          <Star
            className={`h-4 w-4 ${
              value != null && value >= step
                ? 'fill-yellow-400 text-yellow-400'
                : 'text-muted-foreground'
            }`}
          />
        </button>
      ))}
    </div>
  )
}

export default function WatchPanel({ movieId }: Props) {
  const queryClient = useQueryClient()
  const [rating, setRating] = useState<number | null>(null)

  const watchesQuery = useQuery({
    queryKey: ['watch-log', movieId],
    queryFn: () => fetchWatches(movieId),
    enabled: movieId.length > 0,
  })

  const entries = watchesQuery.data?.items ?? []

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ['watch-log', movieId] })
    // The grid badges watched state and the facet filters on it, so both are stale
    // the moment a watch is logged.
    void queryClient.invalidateQueries({ queryKey: ['movies'] })
    void queryClient.invalidateQueries({ queryKey: ['search'] })
  }

  const log = useMutation({
    mutationFn: () =>
      logWatch({
        movieId,
        // The second and later entries for a film are rewatches, which is what makes
        // Batch 37's "you watched this X years ago" answerable later.
        isRewatch: entries.length > 0,
        personalRating: rating,
      }),
    onSuccess: () => {
      setRating(null)
      refresh()
    },
  })

  const remove = useMutation({
    mutationFn: (entryId: string) => deleteWatch(entryId),
    onSuccess: refresh,
  })

  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-foreground">Watch log</h2>
        <div className="flex items-center gap-3">
          <Stars value={rating} onChange={setRating} />
          <button
            type="button"
            onClick={() => log.mutate()}
            disabled={log.isPending}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground disabled:opacity-60"
          >
            {log.isPending ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <Eye className="h-3 w-3" />
            )}
            {entries.length > 0 ? 'Log a rewatch' : 'Mark watched'}
          </button>
        </div>
      </div>

      {log.isError && (
        <p className="text-xs text-destructive">
          {log.error instanceof Error ? log.error.message : 'Could not log that watch.'}
        </p>
      )}

      {watchesQuery.isLoading ? (
        <p className="text-xs text-muted-foreground">Loading your watch history…</p>
      ) : entries.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          You have not logged a watch for this film.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="flex items-center justify-between gap-3 rounded-lg bg-muted/50 px-3 py-2 text-xs"
            >
              <span className="text-foreground">
                {formatWatchedAt(entry.watchedAt)}
                {entry.isRewatch && (
                  <span className="ml-2 text-muted-foreground">rewatch</span>
                )}
              </span>
              <span className="flex items-center gap-3">
                {entry.personalRating != null && (
                  <span className="inline-flex items-center gap-1 text-yellow-500">
                    <Star className="h-3 w-3 fill-yellow-400 text-yellow-400" />
                    {entry.personalRating}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => remove.mutate(entry.id)}
                  disabled={remove.isPending}
                  aria-label="Remove this watch"
                  className="text-muted-foreground hover:text-destructive disabled:opacity-60"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
