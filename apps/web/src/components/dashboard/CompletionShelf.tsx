import { useQuery } from '@tanstack/react-query'
import { Target } from 'lucide-react'
import type { CompletionSet } from '@mcu/shared'

import { ShelfHeading, ShelfLink } from '@/components/dashboard/Shelf'
import { StatePanel } from '@/components/ui/state-panel'
import { completionCountLabel, fetchCompletionInsights, setTypeLabel } from '@/lib/api'
import { closestToComplete } from '@/lib/home'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/** AC2: the three closest, as a list; the full view has the rest. */
const SHOWN = 3

/** How many missing films a set names on Home; the rest are "+N" and its page. */
const NAMED = 3

/**
 * One set as one block that opens it — AF2 (#372, superseding AE3's buttons on Home, #358): its
 * name, how much is on the shelf and a bar, then one line naming what it is missing, up to three
 * films and "+N". Want and "Doesn't count" are on the set's page, where they have room. A set
 * whose only missing films do not count is complete, and leaves the row.
 */
function SetRow({ set, onOpen }: { set: CompletionSet; onOpen: () => void }) {
  const named = set.missingFilms.slice(0, NAMED)
  const more = set.missingCount - named.length
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="touch-target block w-full rounded-md py-3 text-left transition-colors hover:text-primary"
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
        {/* Only where the answer names films: an older answer names none, and the line above
            already says how many. "+N" stays in sight however long the titles run. */}
        {named.length > 0 ? (
          <span className="mt-2 flex items-start gap-2 text-xs leading-5">
            <span className="line-clamp-2 min-w-0 flex-1 text-foreground">
              <span className="text-muted-foreground">Missing: </span>
              {named.map((film) => `${film.title}${film.year ? ` (${String(film.year)})` : ''}`).join(', ')}
            </span>
            {more > 0 ? <span className="shrink-0 font-semibold text-primary">+{more}</span> : null}
          </span>
        ) : null}
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
    <section aria-labelledby="home-completion" className="archive-panel space-y-1 p-4">
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
