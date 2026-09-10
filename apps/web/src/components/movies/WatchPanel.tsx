import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, Loader2, Star, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import { deleteWatch, fetchWatches, logWatch, RATING_STEPS } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

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
    <div className="flex items-center" role="group" aria-label="Rating for this watch">
      {RATING_STEPS.filter((step) => Number.isInteger(step)).map((step) => (
        <button
          key={step}
          type="button"
          // Clicking the star you already chose clears the rating — otherwise a
          // rating given by accident can only be changed, never removed.
          onClick={() => onChange(value === step ? null : step)}
          aria-label={`${step} star${step === 1 ? '' : 's'}`}
          aria-pressed={value != null && value >= step}
          className="touch-target inline-flex h-11 w-11 items-center justify-center rounded-md hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring/30"
        >
          <Star
            className={`h-5 w-5 ${
              value != null && value >= step
                ? 'fill-accent text-accent'
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
  const state = listState(watchesQuery, entries.length === 0)
  const canLog = state === 'ready' || state === 'empty'

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
    <section className="archive-panel space-y-4 p-4 sm:p-5" aria-busy={watchesQuery.isPending}>
      <div>
        <p className="page-kicker">Personal history</p>
        <h2 className="section-heading">Watch log</h2>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="overflow-x-auto">
          <Stars value={rating} onChange={setRating} />
        </div>
        <Button
          type="button"
          size="sm"
          onClick={() => log.mutate()}
          disabled={log.isPending || !canLog}
          className="w-full sm:w-auto"
        >
          {log.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <Eye aria-hidden />
          )}
          {canLog && entries.length > 0 ? 'Log a rewatch' : 'Mark watched'}
        </Button>
      </div>

      {log.isError && (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(log.error, 'Could not log that watch.')}
        </p>
      )}

      {remove.isError ? (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(remove.error, 'Could not remove that watch.')}
        </p>
      ) : null}

      {state === 'loading' ? (
        <StatePanel
          tone="loading"
          title="Loading watch history"
          description="Checking your private watch log…"
          compact
        />
      ) : state === 'offline' ? (
        <StatePanel
          tone="offline"
          title="Watch history is unavailable offline"
          description="Reconnect to check whether this is a rewatch."
          action={<Button type="button" size="sm" variant="outline" onClick={() => void watchesQuery.refetch()}>Try again</Button>}
          compact
        />
      ) : state === 'error' ? (
        <StatePanel
          tone="error"
          title="Could not load your watch history"
          description={queryErrorMessage(watchesQuery.error, 'The watch log did not respond.')}
          action={<Button type="button" size="sm" variant="outline" onClick={() => void watchesQuery.refetch()}>Try again</Button>}
          compact
        />
      ) : state === 'empty' ? (
        <StatePanel
          tone="empty"
          title="No watches logged"
          description="Rate the film if you like, then mark it as watched."
          compact
        />
      ) : (
        <ul className="space-y-1.5">
          {entries.map((entry) => (
            <li
              key={entry.id}
              className="flex min-h-11 items-center justify-between gap-3 rounded-md bg-muted/50 px-3 py-2 text-sm"
            >
              <span className="text-foreground">
                <time dateTime={entry.watchedAt}>{formatWatchedAt(entry.watchedAt)}</time>
                {entry.isRewatch && (
                  <span className="ml-2 text-muted-foreground">rewatch</span>
                )}
              </span>
              <span className="flex items-center gap-3">
                {entry.personalRating != null && (
                  <span className="inline-flex items-center gap-1 text-accent">
                    <Star className="h-3 w-3 fill-accent text-accent" aria-hidden />
                    {entry.personalRating}
                  </span>
                )}
                <Button
                  type="button"
                  onClick={() => remove.mutate(entry.id)}
                  disabled={remove.isPending}
                  aria-label={`Remove watch from ${formatWatchedAt(entry.watchedAt)}`}
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 text-muted-foreground hover:text-destructive"
                >
                  <Trash2 aria-hidden />
                </Button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
