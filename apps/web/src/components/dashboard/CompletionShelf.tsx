import { useQuery } from '@tanstack/react-query'
import { Target } from 'lucide-react'
import type { CompletionSet } from '@mcu/shared'

import { ShelfHeading, ShelfLink } from '@/components/dashboard/Shelf'
import { StatePanel } from '@/components/ui/state-panel'
import { completionCountLabel, fetchCompletionInsights, setTypeLabel } from '@/lib/api'
import { closestToComplete } from '@/lib/home'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/** How many sets Home shows; the rest are one tap away on the full view. */
/** AC2: the three closest, as a list; the full view has the rest. */
const SHOWN = 3

function SetRow({ set, onOpen }: { set: CompletionSet; onOpen: () => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="touch-target block w-full rounded-md py-2 text-left transition-colors hover:text-primary"
      >
        <span className="flex items-baseline justify-between gap-3 text-sm">
          <span className="min-w-0 truncate font-semibold text-foreground">{set.setName}</span>
          <span className="shrink-0 tabular-nums text-muted-foreground">{completionCountLabel(set)}</span>
        </span>
        <span className="mt-0.5 block text-xs text-muted-foreground">
          {setTypeLabel(set.setType)} · {set.missingCount === 0 ? 'Complete' : `${String(set.missingCount)} missing`}
        </span>
        <span
          role="progressbar"
          aria-label={`${set.setName} completion`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={set.percentComplete}
          className="mt-1.5 block h-1.5 w-full overflow-hidden rounded-full bg-muted"
        >
          <span
            className={cn('block h-full rounded-full', set.missingCount === 0 ? 'bg-primary' : 'bg-warning')}
            style={{ width: `${String(set.percentComplete)}%` }}
          />
        </span>
      </button>
    </li>
  )
}

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

  // AC2: a short list rather than a sideways row, so Home's rows stay at most four.
  return (
    <section aria-labelledby="home-completion" className="archive-panel space-y-2 p-4">
      <ShelfHeading
        id="home-completion"
        title="Closest to complete"
        icon={Target}
        caption="Directors' and actors' films on the shelf."
        action={<ShelfLink to="/insights">All {sets.length}</ShelfLink>}
      />
      <ul className="divide-y divide-border">
        {closestToComplete(sets)
          .slice(0, SHOWN)
          .map((set) => (
            <SetRow key={set.id} set={set} onOpen={() => onOpen(set.id)} />
          ))}
      </ul>
    </section>
  )
}
