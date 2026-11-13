import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, MessageSquareText } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Poster } from '@/components/movies/Poster'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/auth'
import { clearCraigNote } from '@/lib/api'
import type { NeedsYouRowData } from '@/lib/needs-you'
import { personPath } from '@/lib/people'
import { queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

const ROW = 'flex min-h-14 min-w-0 flex-1 items-center gap-3 py-2.5 text-foreground'

/** Batch X12a, since AF1 a row of Needs you: a line stays until Craig has read it and says so. */
function ClearNote({ noteId, title }: { noteId: string; title: string }) {
  const queryClient = useQueryClient()
  const clear = useMutation({
    mutationFn: () => clearCraigNote(noteId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['attention'] }),
  })
  return (
    <span className="shrink-0">
      {/* The line's words are in the accessible name only, so the page never says them twice. */}
      <Button type="button" size="sm" variant="outline" aria-label={`Clear: ${title}`} disabled={clear.isPending} onClick={() => clear.mutate()}>
        Clear
      </Button>
      {clear.isError ? <span role="alert" className="mt-1 block text-xs text-destructive">{queryErrorMessage(clear.error, 'That could not be cleared. Try again.')}</span> : null}
    </span>
  )
}

/** What leads a row: the film's poster, or for the app's own rows a sign of what they are. */
function Face({ row }: { row: NeedsYouRowData }) {
  if (row.kind === 'app' || row.kind === 'note') {
    const Icon = row.kind === 'app' ? AlertTriangle : MessageSquareText
    return (
      <span aria-hidden className={cn('flex h-12 w-8 shrink-0 items-center justify-center rounded-sm border', row.kind === 'app' ? 'border-warning/60 bg-warning/10 text-warning' : 'border-border bg-muted text-muted-foreground')}>
        <Icon className="size-4" />
      </span>
    )
  }
  return <Poster path={row.poster} title={row.film} size="w92" decorative className="h-12 w-8 shrink-0 rounded-sm border border-border" />
}

function Words({ row }: { row: NeedsYouRowData }) {
  return (
    <span className="min-w-0 flex-1">
      <span className="line-clamp-2 break-words text-sm font-semibold">{row.title}</span>
      <span className="mt-0.5 block text-xs text-muted-foreground">{row.detail}</span>
    </span>
  )
}

/** Whose it is: a link to that person's page, or to You for the reader's own; "App" is nobody's. */
function Label({ row }: { row: NeedsYouRowData }) {
  const { profile } = useAuth()
  const chip = cn(
    'rounded-full px-2 py-0.5 text-xs font-semibold',
    row.kind === 'app' ? 'bg-warning/15 text-warning' : row.own ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground',
  )
  if (row.kind === 'app' || !row.ownerId) return <span className={cn('shrink-0', chip)}>{row.label}</span>
  return (
    <Link
      to={personPath(row.ownerId, profile?.id)}
      aria-label={row.own ? 'Yours: open You' : `${row.label}’s: open their page`}
      className="touch-target inline-flex min-h-11 shrink-0 items-center"
    >
      <span className={chip}>{row.label}</span>
    </Link>
  )
}

/** Needs you's rows, each with whose it is — AE8 (#355). Home shows five; the Needs you page
 *  shows every one. Each opens its own page, where only its owner can act. Since AE9 the label
 *  is a link of its own, to that person's page, or to You for the reader's own. Since AF1 (#372)
 *  Craig's list carries the app's problems, labelled App, and the lines sent to him, with Clear. */
export function NeedsYouList({ rows, className }: { rows: NeedsYouRowData[]; className?: string }) {
  return (
    <ul className={cn('divide-y divide-border', className)}>
      {rows.map((row) => (
        <li key={row.key} className="flex items-center gap-2">
          {row.to ? (
            <Link to={row.to} className={cn('touch-target hover:text-primary', ROW)}>
              <Face row={row} />
              <Words row={row} />
            </Link>
          ) : (
            <div className={ROW}>
              <Face row={row} />
              <Words row={row} />
            </div>
          )}
          {row.noteId ? <ClearNote noteId={row.noteId} title={row.title} /> : null}
          <Label row={row} />
        </li>
      ))}
    </ul>
  )
}
