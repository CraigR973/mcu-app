import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Poster } from '@/components/movies/Poster'
import type { NeedsYouRowData } from '@/lib/needs-you'
import { cn } from '@/lib/utils'

/** Needs you's rows, each with whose it is — AE8 (#355). Home shows five; the Needs you page
 *  shows every one. Each opens its own page, where only its owner can act. */
export function NeedsYouList({ rows, className }: { rows: NeedsYouRowData[]; className?: string }) {
  return (
    <ul className={cn('divide-y divide-border', className)}>
      {rows.map((row) => (
        <li key={row.key}>
          <Link to={row.to} className="touch-target flex min-h-14 items-center gap-3 py-2.5 text-foreground hover:text-primary">
            <Poster path={row.poster} title={row.film} size="w92" decorative className="h-12 w-8 shrink-0 rounded-sm border border-border" />
            <span className="min-w-0 flex-1">
              <span className="line-clamp-2 text-sm font-semibold">{row.title}</span>
              <span className="mt-0.5 block text-xs text-muted-foreground">{row.detail}</span>
            </span>
            <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold', row.own ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground')}>
              {row.label}
            </span>
            <ChevronRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
          </Link>
        </li>
      ))}
    </ul>
  )
}
