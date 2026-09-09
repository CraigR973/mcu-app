import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, RotateCcw, Trash2, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { TrashRow, TrashTable } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import {
  destroyTrashRow,
  fetchTrashTable,
  posterUrl,
  purgeTrash,
  restoreTrashRow,
  TRASH_TABLE_LABELS,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

const TABLES: TrashTable[] = [
  'collection_items',
  'watch_log',
  'movies',
  'box_sets',
  // Batch 18. Batch 15 refused these two by name rather than answering an empty page for
  // tables that did not exist; §3.5 and §3.16 exist now.
  'wanted_list',
  'retailers',
  'gift_links',
]

/** Every query a restore or a destroy can change. Listed once so a new tab cannot forget one. */
function invalidateEverything(queryClient: ReturnType<typeof useQueryClient>) {
  for (const key of [
    'trash',
    'trash-table',
    'movies',
    'search',
    'facets',
    'collection-facets',
    'stats',
    'activity',
    'box-sets',
    'loans',
    'completion-insights',
    'wanted',
    'retailers',
  ]) {
    void queryClient.invalidateQueries({ queryKey: [key] })
  }
}

function Row({ row, table }: { row: TrashRow; table: TrashTable }) {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)

  const restore = useMutation({
    mutationFn: () => restoreTrashRow(table, row.id),
    onSuccess: () => invalidateEverything(queryClient),
  })
  const destroy = useMutation({
    mutationFn: () => destroyTrashRow(table, row.id),
    onSuccess: () => {
      setConfirming(false)
      invalidateEverything(queryClient)
    },
  })

  return (
    <li className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
      {row.posterPath !== null || row.movieId !== null ? (
        <img
          src={posterUrl(row.posterPath, 'w92')}
          alt=""
          loading="lazy"
          className="h-16 w-11 shrink-0 rounded object-cover"
        />
      ) : null}
      <div className="min-w-0 flex-1">
        {row.movieId ? (
          <Link
            to={`/movies/${row.movieId}`}
            className="font-medium text-foreground hover:underline"
          >
            {row.label}
          </Link>
        ) : (
          <span className="font-medium text-foreground">{row.label}</span>
        )}
        {row.sublabel ? (
          <p className="text-xs text-muted-foreground">{row.sublabel}</p>
        ) : null}
        <p className="text-[11px] text-muted-foreground">
          Removed {new Date(row.deletedAt).toLocaleString()}
        </p>
        {destroy.isError ? (
          <p className="text-xs text-destructive">
            {queryErrorMessage(destroy.error, 'Could not delete permanently.')}
          </p>
        ) : null}
      </div>

      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={restore.isPending}
        onClick={() => restore.mutate()}
      >
        {restore.isPending ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <RotateCcw className="h-4 w-4" />
        )}
        Restore
      </Button>

      {/* Two clicks, never one. This is the only irreversible control in the app, and the
          confirming state names what will happen rather than asking "are you sure?". */}
      {confirming ? (
        <div className="flex shrink-0 gap-1">
          <Button
            type="button"
            size="sm"
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={destroy.isPending}
            onClick={() => destroy.mutate()}
          >
            {destroy.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <TriangleAlert className="h-4 w-4" />
            )}
            Destroy for ever
          </Button>
          <Button type="button" size="sm" variant="ghost" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label="Delete permanently"
          onClick={() => setConfirming(true)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      )}
    </li>
  )
}

function PurgePanel({ table }: { table: TrashTable }) {
  const queryClient = useQueryClient()
  const [armed, setArmed] = useState(false)

  const preview = useMutation({
    mutationFn: () => purgeTrash(table, true),
    onSuccess: () => setArmed(true),
  })
  const run = useMutation({
    mutationFn: () => purgeTrash(table, false),
    onSuccess: () => {
      setArmed(false)
      invalidateEverything(queryClient)
    },
  })

  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/30 p-3">
      <p className="text-xs text-muted-foreground">
        §6.30 says anything deleted more than 90 days ago is purged. Nothing here is
        automatic — a timer that permanently destroys rows is not something to add without
        someone deciding to.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={preview.isPending}
          onClick={() => preview.mutate()}
        >
          {preview.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          What would be purged?
        </Button>
        {preview.data ? (
          <span className="text-xs text-muted-foreground">
            {preview.data.count} row{preview.data.count === 1 ? '' : 's'} older than{' '}
            {preview.data.olderThanDays} days
          </span>
        ) : null}
        {armed && preview.data && preview.data.count > 0 ? (
          <Button
            type="button"
            size="sm"
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={run.isPending}
            onClick={() => run.mutate()}
          >
            {run.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <TriangleAlert className="h-4 w-4" />
            )}
            Purge {preview.data.count} for ever
          </Button>
        ) : null}
      </div>
      {run.data ? (
        <p className="text-xs text-muted-foreground">Purged {run.data.deleted}.</p>
      ) : null}
    </div>
  )
}

/**
 * §13.5's Trash — now across every table that soft-deletes, with restore and permanent
 * delete.
 *
 * **All six tables §6.30 implies are here since Batch 18.** Batch 15 shipped four and made
 * the API *refuse* `wanted_list` by name rather than answer "nothing here" for a table that
 * did not exist — which is how an unimplemented feature passes for a working one. §3.5 and
 * §3.16 exist now, so the refusal became two more tabs rather than a lie that had to be
 * unwound.
 */
export default function TrashPage() {
  const [table, setTable] = useState<TrashTable>('collection_items')

  const trashQuery = useQuery({
    queryKey: ['trash-table', table],
    queryFn: () => fetchTrashTable(table),
  })
  const rows = trashQuery.data?.items ?? []
  const counts = trashQuery.data?.counts ?? []
  const state = listState(trashQuery, rows.length === 0)

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Trash</h1>
        <p className="text-sm text-muted-foreground">
          Anything removed. Restoring brings it back exactly as it was; destroying does not.
        </p>
      </div>

      <div className="flex flex-wrap gap-1">
        {TABLES.map((candidate) => {
          const count = counts.find((entry) => entry.table === candidate)?.count
          return (
            <button
              key={candidate}
              type="button"
              onClick={() => setTable(candidate)}
              className={cn(
                'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                table === candidate
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted',
              )}
            >
              {TRASH_TABLE_LABELS[candidate]}
              {count === undefined ? '' : ` (${String(count)})`}
            </button>
          )
        })}
      </div>

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the trash could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(trashQuery.error, 'Could not load the trash.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <Trash2 className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            Nothing has been removed from {TRASH_TABLE_LABELS[table].toLowerCase()}.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <Row key={row.id} row={row} table={table} />
          ))}
        </ul>
      )}

      <PurgePanel table={table} />
    </div>
  )
}
