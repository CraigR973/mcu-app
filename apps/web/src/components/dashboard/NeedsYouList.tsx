import { Link } from 'react-router-dom'

import { Poster } from '@/components/movies/Poster'
import { useAuth } from '@/context/auth'
import type { NeedsYouRowData } from '@/lib/needs-you'
import { personPath } from '@/lib/people'
import { cn } from '@/lib/utils'

/** Needs you's rows, each with whose it is — AE8 (#355). Home shows five; the Needs you page
 *  shows every one. Each opens its own page, where only its owner can act. Since AE9 the label
 *  is a link of its own, to that person's page, or to You for the reader's own. */
export function NeedsYouList({ rows, className }: { rows: NeedsYouRowData[]; className?: string }) {
  const { profile } = useAuth()
  return (
    <ul className={cn('divide-y divide-border', className)}>
      {rows.map((row) => (
        <li key={row.key} className="flex items-center gap-2">
          <Link to={row.to} className="touch-target flex min-h-14 min-w-0 flex-1 items-center gap-3 py-2.5 text-foreground hover:text-primary">
            <Poster path={row.poster} title={row.film} size="w92" decorative className="h-12 w-8 shrink-0 rounded-sm border border-border" />
            <span className="min-w-0 flex-1">
              <span className="line-clamp-2 text-sm font-semibold">{row.title}</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">{row.detail}</span>
            </span>
          </Link>
          {row.ownerId ? (
            <Link
              to={personPath(row.ownerId, profile?.id)}
              aria-label={row.own ? 'Yours: open You' : `${row.label}’s: open their page`}
              className="touch-target inline-flex min-h-11 shrink-0 items-center"
            >
              <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold', row.own ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground')}>
                {row.label}
              </span>
            </Link>
          ) : (
            <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold', row.own ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground')}>
              {row.label}
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}
