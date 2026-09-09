import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ScrollText } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { AuditEntry } from '@mcu/shared'

import { fetchAudit } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

const ACTIONS = ['', 'create', 'update', 'delete', 'restore', 'bulk_import'] as const

function Diff({ changes }: { changes: Record<string, unknown> | null }) {
  if (!changes || Object.keys(changes).length === 0) {
    return <p className="text-[11px] text-muted-foreground">no field changes recorded</p>
  }
  return (
    <ul className="space-y-0.5">
      {Object.entries(changes).map(([field, value]) => {
        // A diff entry is `{from, to}`; a create/delete snapshot is a bare value. Both
        // shapes are real (`diff_snapshots` writes the first, `item_snapshot` the second),
        // so the renderer has to tell them apart rather than assume.
        const move =
          value !== null && typeof value === 'object' && 'from' in value && 'to' in value
            ? (value as { from: unknown; to: unknown })
            : null
        return (
          <li key={field} className="text-[11px] text-muted-foreground">
            <span className="text-foreground">{field.replaceAll('_', ' ')}</span>
            {move ? (
              <>
                : <span className="line-through">{render(move.from)}</span> →{' '}
                <span className="text-foreground">{render(move.to)}</span>
              </>
            ) : (
              <>: {render(value)}</>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function render(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (Array.isArray(value)) return value.length === 0 ? '—' : value.join(' + ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function Row({ entry }: { entry: AuditEntry }) {
  return (
    <li className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm text-foreground">
          <span className="font-medium">{entry.actorName ?? 'A deleted profile'}</span>{' '}
          <span className="text-muted-foreground">{entry.actionType}</span>{' '}
          <span className="text-muted-foreground">
            {entry.targetTable.replaceAll('_', ' ')}
          </span>
        </p>
        <time className="shrink-0 text-[11px] text-muted-foreground" dateTime={entry.createdAt}>
          {new Date(entry.createdAt).toLocaleString()}
        </time>
      </div>
      <div className="mt-1">
        <Diff changes={entry.changes} />
      </div>
    </li>
  )
}

/**
 * §13.6's audit log UI — "filterable log of all admin actions".
 *
 * It reads Batch 7's `GET /admin/audit` rather than a new endpoint; this batch added the
 * `actorId` and date filters it lacked. An entry whose actor has been deleted still
 * renders: `admin_actions.user_id` is SET NULL precisely so the log can still say what
 * happened when it can no longer say who (`DECISIONS.md` #5).
 */
export default function AuditPage() {
  const [action, setAction] = useState<string>('')
  const [since, setSince] = useState<string>('')

  const auditQuery = useQuery({
    queryKey: ['audit', action, since],
    queryFn: () =>
      fetchAudit({
        actionType: action || undefined,
        since: since ? `${since}T00:00:00Z` : undefined,
        perPage: 100,
      }),
  })
  const entries = auditQuery.data?.items ?? []
  const state = listState(auditQuery, entries.length === 0)

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Audit log</h1>
        <p className="text-sm text-muted-foreground">
          Every change anyone has made, with what moved.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {ACTIONS.map((value) => (
          <button
            key={value || 'all'}
            type="button"
            onClick={() => setAction(value)}
            className={cn(
              'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              action === value
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-muted',
            )}
          >
            {value === '' ? 'All' : value.replaceAll('_', ' ')}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground">
          Since
          <input
            type="date"
            value={since}
            onChange={(event) => setSince(event.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground"
          />
        </label>
      </div>

      {state === 'loading' ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : state === 'offline' ? (
        <p className="text-sm text-muted-foreground">
          Waiting for the network — the audit log could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-sm text-destructive">
          {queryErrorMessage(auditQuery.error, 'Could not load the audit log.')}
        </p>
      ) : state === 'empty' ? (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <ScrollText className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">Nothing matches those filters.</p>
        </div>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            {auditQuery.data?.total.toLocaleString()} entries
          </p>
          <ul className="space-y-2">
            {entries.map((entry) => (
              <Row key={entry.id} entry={entry} />
            ))}
          </ul>
        </>
      )}
      <p className="text-[11px] text-muted-foreground">
        Looking for a single disc&rsquo;s history? It is on the{' '}
        <Link to="/movies" className="text-primary hover:underline">
          film&rsquo;s own page
        </Link>
        .
      </p>
    </div>
  )
}
