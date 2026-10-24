import { useQuery } from '@tanstack/react-query'
import { Target } from 'lucide-react'
import type { CompletionSet } from '@mcu/shared'

import { Shelf, ShelfLink } from '@/components/dashboard/Shelf'
import { StatePanel } from '@/components/ui/state-panel'
import { completionCountLabel, fetchCompletionInsights, posterUrl, setTypeLabel } from '@/lib/api'
import { closestToComplete } from '@/lib/home'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/** How many sets Home shows; the rest are one tap away on the full view. */
const SHOWN = 12

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
}

function SetCard({ set, onOpen }: { set: CompletionSet; onOpen: () => void }) {
  return (
    <li className="w-60 shrink-0 snap-start">
      <button
        type="button"
        onClick={onOpen}
        className="h-full w-full rounded-lg border border-border bg-card p-3 text-left transition-colors hover:border-primary/40"
      >
        <div className="flex items-center gap-2">
          {set.personProfilePath ? (
            <img src={posterUrl(set.personProfilePath, 'w185')} alt="" className="h-9 w-9 rounded-full object-cover" />
          ) : (
            <div aria-hidden className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground">{initials(set.setName)}</div>
          )}
          <span className="block truncate font-medium text-foreground">{set.setName}</span>
        </div>
        <span className="mt-0.5 block text-xs text-muted-foreground">
          {setTypeLabel(set.setType)} · {completionCountLabel(set)}
        </span>
        <span
          role="progressbar"
          aria-label={`${set.setName} completion`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={set.percentComplete}
          className="my-2 block h-1.5 w-full overflow-hidden rounded-full bg-muted"
        >
          <span
            className={cn('block h-full rounded-full', set.missingCount === 0 ? 'bg-primary' : 'bg-warning')}
            style={{ width: `${String(set.percentComplete)}%` }}
          />
        </span>
        <span className="block text-xs text-muted-foreground">
          {set.missingCount === 0 ? 'Complete' : `${String(set.missingCount)} missing`} · {set.percentComplete}%
        </span>
      </button>
    </li>
  )
}

/**
 * Completion on Home — Batch W2, as a row of cards closest to complete first (#249).
 *
 * A card opens that set, in place of Home, through `onOpen`: Home owns which set is open.
 * Until W2 the list owned it and Home swapped in a second copy of the list while a set was
 * open, which started with nothing open, so the first tap showed the whole list again. "All"
 * opens the full view at `/insights`, the old Insights page's address, with its filters and
 * Craig's refresh.
 */
export function CompletionShelf({ onOpen }: { onOpen: (setId: string) => void }) {
  // The same key as the full view's unfiltered list, so the two share one request.
  const query = useQuery({
    queryKey: ['completion-insights', ''],
    queryFn: () => fetchCompletionInsights(undefined),
  })
  const sets = query.data?.items ?? []
  const state = listState(query, sets.length === 0)

  if (state === 'offline') {
    return (
      <StatePanel
        compact
        tone="offline"
        title="Completion sets are not cached here"
        description="Reconnect to load them on this device."
      />
    )
  }
  if (state === 'error') {
    return (
      <StatePanel
        compact
        tone="error"
        title="Completion sets are unavailable"
        description={queryErrorMessage(query.error, 'Could not load the completion sets.')}
      />
    )
  }
  // Hidden while loading or empty, as Home's other rows are (#154).
  if (state !== 'ready') return null

  return (
    <Shelf
      id="home-completion"
      title="Completion"
      icon={Target}
      caption="How much of each director's and actor's work is on the shelf, closest to complete first."
      action={<ShelfLink to="/insights">All {sets.length}</ShelfLink>}
    >
      {closestToComplete(sets)
        .slice(0, SHOWN)
        .map((set) => (
          <SetCard key={set.id} set={set} onOpen={() => onOpen(set.id)} />
        ))}
    </Shelf>
  )
}
