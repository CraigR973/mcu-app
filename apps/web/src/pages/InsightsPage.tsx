import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, RefreshCw, Target } from 'lucide-react'
import type { CompletionSet } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/auth'
import {
  completionCountLabel,
  fetchCompletionInsights,
  refreshCompletionSets,
  setTypeLabel,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

import { CompletionSetPanel } from '@/components/insights/CompletionSetPanel'

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
        <div className="my-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              'h-full rounded-full',
              set.percentComplete === 100 ? 'bg-primary' : 'bg-amber-500',
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
 * **There is no "add missing to wanted list" button.** §11.2's bullet list asks for one,
 * and the wanted list does not exist: §3.5 designs `wanted_list`, Batch 18 builds it, and
 * `/watchlist` is still a "coming soon" stub. Shipping the button would mean shipping a
 * control that does nothing — the defect `STATUS.md` gotcha 5 catalogues four instances of
 * in the onboarding wizard, and the one Batch 9 refused to repeat (`DECISIONS.md` #50).
 * Batch 18 owns adding it. §11.2's *acceptance criterion* does not mention it.
 */
export default function InsightsPage() {
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

  if (openSetId !== null) {
    return <CompletionSetPanel setId={openSetId} onBack={() => setOpenSetId(null)} />
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 md:p-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Insights</h1>
          <p className="text-sm text-muted-foreground">
            How much of each director&rsquo;s and actor&rsquo;s work is on the shelf.
          </p>
        </div>
        {profile?.role === 'admin' ? (
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
        ) : null}
      </div>

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
              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              filter === option.value
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-muted',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the insights could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(insightsQuery.error, 'Could not load the insights.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Target className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            No completion sets yet.
            {profile?.role === 'admin'
              ? ' Refresh from TMDB to build them from the collection’s own credits.'
              : ''}
          </p>
        </div>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {sets.length} sets
            {insightsQuery.data?.oldestRefresh
              ? ` · oldest refreshed ${new Date(insightsQuery.data.oldestRefresh).toLocaleDateString()}`
              : ''}
          </p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {sets.map((set) => (
              <SetRow key={set.id} set={set} onOpen={() => setOpenSetId(set.id)} />
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
