import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ScrollText } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { AuditEntry } from '@mcu/shared'

import { PageHeader } from '@/components/ui/page-header'
import { StatePanel } from '@/components/ui/state-panel'
import { fetchAudit } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn, formatDateTime } from '@/lib/utils'

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
          <li key={field} className="break-words text-xs leading-5 text-muted-foreground">
            <span className="font-medium text-foreground">{field.replaceAll('_', ' ')}</span>
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
    <li className="archive-panel p-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-4">
        <p className="min-w-0 text-sm leading-6 text-foreground">
          <span className="font-medium">{entry.actorName ?? 'A deleted profile'}</span>{' '}
          <span className="font-medium text-primary">{entry.actionType.replaceAll('_', ' ')}</span>{' '}
          <span className="text-muted-foreground">
            {entry.targetTable.replaceAll('_', ' ')}
          </span>
        </p>
        <time className="shrink-0 text-xs tabular-nums text-muted-foreground" dateTime={entry.createdAt}>
          {formatDateTime(entry.createdAt)}
        </time>
      </div>
      <div className="mt-3 border-t border-border pt-3">
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
    <div className="page-shell-narrow space-y-7">
      <PageHeader
        eyebrow="Administrator"
        title="Audit log"
        description="A permanent, filterable record of collection changes and who made them."
      />

      <div className="archive-panel flex flex-col gap-4 p-4 sm:p-5">
        <fieldset>
          <legend className="field-label">Action</legend>
          <div className="flex flex-wrap gap-1.5">
            {ACTIONS.map((value) => (
              <button
                key={value || 'all'}
                type="button"
                onClick={() => setAction(value)}
                aria-pressed={action === value}
                className={cn(
                  'touch-target min-h-10 rounded-md border px-3 py-2 text-xs font-semibold capitalize transition-colors',
                  action === value
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-transparent text-muted-foreground hover:border-border hover:bg-muted hover:text-foreground',
                )}
              >
                {value === '' ? 'All' : value.replaceAll('_', ' ')}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="block max-w-56 text-sm text-muted-foreground">
          <span className="field-label">From date</span>
          <input
            type="date"
            value={since}
            onChange={(event) => setSince(event.target.value)}
            className="form-control"
          />
        </label>
      </div>

      {state === 'loading' ? (
        <StatePanel tone="loading" title="Opening the audit ledger" />
      ) : state === 'offline' ? (
        <StatePanel tone="offline" title="The audit ledger is not cached here" description="Reconnect to inspect the administrative history." />
      ) : state === 'error' ? (
        <StatePanel
          tone="error"
          title="The audit ledger is unavailable"
          description={queryErrorMessage(auditQuery.error, 'Could not load the audit log.')}
        />
      ) : state === 'empty' ? (
        <StatePanel
          tone="empty"
          icon={ScrollText}
          title="Nothing matches these filters"
          description="Choose another action or move the start date earlier."
        />
      ) : (
        <>
          <p role="status" className="metadata-label">
            {auditQuery.data?.total.toLocaleString()} entries
          </p>
          <ul className="space-y-3">
            {entries.map((entry) => (
              <Row key={entry.id} entry={entry} />
            ))}
          </ul>
        </>
      )}
      <p className="border-t border-border pt-5 text-xs leading-5 text-muted-foreground">
        Looking for a single disc&rsquo;s history? It is on the{' '}
        <Link to="/movies" className="text-primary hover:underline">
          film&rsquo;s own page
        </Link>
        .
      </p>
    </div>
  )
}
