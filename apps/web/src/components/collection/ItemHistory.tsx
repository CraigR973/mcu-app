import { useQuery } from '@tanstack/react-query'
import { History } from 'lucide-react'
import { auditFieldChangeSchema } from '@mcu/shared'

import { conditionLabel, fetchAudit, formatLabel, type AuditEntry } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

interface Props {
  movieId: string
}

const ACTION_LABELS: Record<string, string> = {
  create: 'Added',
  update: 'Edited',
  delete: 'Moved to trash',
  restore: 'Restored from trash',
  bulk_import: 'Imported',
}

/** Field names as a person would say them. Anything not listed falls back to the
 *  column name with underscores removed, which is still readable. */
const FIELD_LABELS: Record<string, string> = {
  formats: 'Format',
  location: 'Location',
  section: 'Section',
  shelf: 'Shelf',
  sub_category: 'Collector edition',
  notes: 'Notes',
  condition: 'Condition',
  has_playback_issues: 'Playback issues',
  playback_notes: 'Playback notes',
  purchase_price: 'Price paid',
  purchase_source: 'Bought from',
  purchase_date: 'Bought on',
  duplicate_reason: 'Added because',
}

function render(field: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (Array.isArray(value)) {
    return value.map((entry) => formatLabel(String(entry)) ?? String(entry)).join(' + ')
  }
  if (field === 'condition') return conditionLabel(String(value)) ?? String(value)
  return String(value)
}

function Changes({ entry }: { entry: AuditEntry }) {
  const changes = entry.changes
  if (!changes) return null

  // An update's `changes` is a diff; a create/delete's is a snapshot. Narrowing each
  // value rather than assuming the shape is what lets one panel render both.
  const lines = Object.entries(changes).flatMap(([field, value]) => {
    const parsed = auditFieldChangeSchema.safeParse(value)
    if (!parsed.success) return []
    return [
      {
        field,
        text: `${render(field, parsed.data.from)} → ${render(field, parsed.data.to)}`,
      },
    ]
  })

  if (lines.length === 0) return null
  return (
    <ul className="mt-1 space-y-0.5">
      {lines.map(({ field, text }) => (
        <li key={field} className="text-xs text-muted-foreground">
          <span className="text-foreground">{FIELD_LABELS[field] ?? field.replaceAll('_', ' ')}</span>
          {': '}
          {text}
        </li>
      ))}
    </ul>
  )
}

/**
 * §3.11's "condition history visible on detail page", widened to the whole history of
 * every disc of this film — including discs that have since been thrown away, which is
 * the history most worth keeping.
 *
 * Admin-only, because `GET /admin/audit` is. The detail page renders this only for an
 * admin rather than letting a viewer watch it fail.
 */
export default function ItemHistory({ movieId }: Props) {
  const historyQuery = useQuery({
    queryKey: ['item-history', movieId],
    queryFn: () => fetchAudit({ movieId }),
    enabled: movieId.length > 0,
  })

  const entries = historyQuery.data?.items ?? []
  const state = listState(historyQuery, entries.length === 0)

  return (
    <section className="space-y-3 rounded-xl border border-border bg-card p-4">
      <h2 className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
        <History className="h-4 w-4" /> History
      </h2>

      {state === 'loading' ? (
        <p className="text-xs text-muted-foreground">Loading history…</p>
      ) : state === 'offline' ? (
        <p className="text-xs text-muted-foreground">
          Waiting for the network — the history could not be loaded yet.
        </p>
      ) : state === 'error' ? (
        <p className="text-xs text-destructive">
          {queryErrorMessage(historyQuery.error, 'Could not load the history.')}
        </p>
      ) : state === 'empty' ? (
        <p className="text-xs text-muted-foreground">
          Nothing has changed since this film was catalogued.
        </p>
      ) : (
        <ol className="space-y-2">
          {entries.map((entry) => (
            <li key={entry.id} className="rounded-lg bg-muted/50 px-3 py-2">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-xs font-medium text-foreground">
                  {ACTION_LABELS[entry.actionType] ?? entry.actionType}
                  {entry.actorName && (
                    <span className="font-normal text-muted-foreground"> by {entry.actorName}</span>
                  )}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {new Date(entry.createdAt).toLocaleString()}
                </span>
              </div>
              <Changes entry={entry} />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
