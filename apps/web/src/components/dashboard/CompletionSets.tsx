import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, RefreshCw } from 'lucide-react'
import type { CompletionSet } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { CompletionSetPanel } from '@/components/insights/CompletionSetPanel'
import { StatePanel } from '@/components/ui/state-panel'
import { useAuth } from '@/context/auth'
import {
  completionCountLabel,
  fetchCompletionInsights,
  refreshCompletionSets,
  setTypeLabel,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

function SetRow({ set, onOpen }: { set: CompletionSet; onOpen: () => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="w-full rounded-lg border border-border bg-card p-3 text-left transition-colors hover:border-primary/40"
      >
        <div className="flex items-baseline justify-between gap-3">
          <span className="truncate font-medium text-foreground">{set.setName}</span>
          <span className="shrink-0 text-xs text-muted-foreground">
            {completionCountLabel(set)}
          </span>
        </div>
        <div role="progressbar" aria-label={`${set.setName} completion`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={set.percentComplete} className="my-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              'h-full rounded-full',
              set.percentComplete === 100 ? 'bg-primary' : 'bg-warning',
            )}
            style={{ width: `${String(set.percentComplete)}%` }}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {setTypeLabel(set.setType)} · {set.missingCount} missing · {set.percentComplete}%
        </p>
      </button>
    </li>
  )
}

/**
 * §11.2's Completion Insights — "≥ 20 sets with owned/missing counts".
 *
 * A section of the merged Home since Batch S3, where it was a page of its own. It is the
 * one part of the three that was never thin: 40 real sets against a Home whose other
 * three sections were all empty, which is half of why the merge is worth doing.
 *
 * **Renders nothing at all when there are no sets** — snag 5's rule for the merged page.
 * The previous page showed an empty-state panel here; on a page assembled from four
 * sections, four such panels *are* the emptiness Craig reported.
 */
export function CompletionSets({ onOpenChange }: { onOpenChange?: (open: boolean) => void }) {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const [openSetId, setOpenSetId] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('')

  const insightsQuery = useQuery({
    queryKey: ['completion-insights', filter],
    queryFn: () => fetchCompletionInsights(filter || undefined),
  })
  const sets = insightsQuery.data?.items ?? []
  const state = listState(insightsQuery, sets.length === 0)

  const refresh = useMutation({
    mutationFn: () => refreshCompletionSets(false),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['completion-insights'] })
      void queryClient.invalidateQueries({ queryKey: ['completion-set'] })
    },
  })

  function open(id: string | null) {
    setOpenSetId(id)
    onOpenChange?.(id !== null)
  }

  if (openSetId !== null) {
    return <CompletionSetPanel setId={openSetId} onBack={() => open(null)} />
  }

  // Hidden rather than rendered empty. An admin who has never refreshed still needs the
  // button, so only a viewer loses the section entirely — for them there is nothing here
  // and nothing they could do about it.
  const isAdmin = profile?.role === 'admin'
  if (state === 'empty' && !isAdmin) return null
  if (state === 'loading') return <StatePanel compact tone="loading" title="Loading completion sets" />
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
        description={queryErrorMessage(insightsQuery.error, 'Could not load the insights.')}
      />
    )
  }

  return (
    <div className="space-y-3">
      {isAdmin ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={refresh.isPending}
            onClick={() => refresh.mutate()}
          >
            {refresh.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh from TMDB
          </Button>
          {refresh.isError ? (
            <p className="text-sm text-destructive">
              {queryErrorMessage(refresh.error, 'The refresh could not be run.')}
            </p>
          ) : null}
          {refresh.isSuccess ? (
            <p className="text-sm text-muted-foreground">
              Refreshed — {refresh.data.created} new, {refresh.data.updated} updated,{' '}
              {refresh.data.unchanged} unchanged
              {refresh.data.errors.length > 0
                ? `, ${String(refresh.data.errors.length)} failed`
                : ''}
              .
            </p>
          ) : null}
        </div>
      ) : null}

      {state === 'empty' ? (
        <p className="text-sm text-muted-foreground">
          No completion sets yet. Refresh from TMDB to build them from the collection&rsquo;s
          own credits.
        </p>
      ) : (
        <>
          <div className="flex gap-1">
            {[
              { value: '', label: 'All' },
              { value: 'director', label: 'Directors' },
              { value: 'actor', label: 'Actors' },
            ].map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => setFilter(option.value)}
                className={cn(
                  'touch-target min-h-11 rounded-md px-3 text-sm font-semibold transition-colors',
                  filter === option.value
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted',
                )}
                aria-pressed={filter === option.value}
              >
                {option.label}
              </button>
            ))}
          </div>

          <p className="text-xs text-muted-foreground">
            {sets.length} sets
            {insightsQuery.data?.oldestRefresh
              ? ` · oldest refreshed ${new Date(insightsQuery.data.oldestRefresh).toLocaleDateString()}`
              : ''}
          </p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {sets.map((set) => (
              <SetRow key={set.id} set={set} onOpen={() => open(set.id)} />
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
