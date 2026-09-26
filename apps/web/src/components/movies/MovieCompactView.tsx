import { useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Copy, MapPin } from 'lucide-react'
import { Link } from 'react-router-dom'

import { StatePanel } from '@/components/ui/state-panel'
import { type MovieListItem } from '@/lib/api'
import { FormatBadge } from './FormatBadge'

interface Props {
  movies: MovieListItem[]
  isLoading: boolean
}

export function MovieCompactView({ movies, isLoading }: Props) {
  const parentRef = useRef<HTMLDivElement>(null)
  const rowHeight = 52
  const rowVirtualizer = useVirtualizer({
    count: isLoading ? 30 : movies.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 12,
  })

  if (!isLoading && movies.length === 0) {
    return <StatePanel tone="empty" title="No films match this view" description="Remove one or more filters to widen the archive selection." className="m-4 flex-1" />
  }

  return (
    <div ref={parentRef} className="min-h-0 flex-1 overflow-y-auto" aria-busy={isLoading}>
      <div style={{ height: rowVirtualizer.getTotalSize() + 96, position: 'relative' }}>
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const positioning = { position: 'absolute' as const, top: virtualRow.start, left: 0, right: 0, height: rowHeight }
          if (isLoading) {
            return (
              <div key={virtualRow.index} style={positioning} className="flex items-center gap-3 border-b border-border/80 px-4">
                <div className="h-3 w-5 shrink-0 animate-pulse rounded-sm bg-muted" />
                <div className="h-3 flex-1 animate-pulse rounded-sm bg-muted" />
                <div className="h-4 w-16 shrink-0 animate-pulse rounded-sm bg-muted" />
              </div>
            )
          }

          const movie = movies[virtualRow.index]
          const locations = movie.locations.map((location) => location.label).join(' · ')
          const editions = movie.editions.join(' · ')
          return (
            <Link key={movie.id} to={`/movies/${movie.id}`} style={positioning} className="group flex items-center gap-2 border-b border-border/80 px-3 transition-colors hover:bg-muted/65 focus-visible:z-10 sm:gap-3 sm:px-4">
              <span className="hidden w-7 shrink-0 text-right font-mono text-[0.6875rem] tabular-nums text-muted-foreground sm:block">{virtualRow.index + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="flex min-w-0 items-baseline gap-2">
                  <span className="truncate text-sm font-semibold text-foreground">{movie.title}</span>
                  <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{movie.year ?? '—'}</span>
                </span>
                <span className="mt-0.5 flex min-w-0 items-center gap-1 truncate text-xs font-medium text-foreground">
                  <MapPin className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
                  <span className="truncate">{locations || 'Location not recorded'}</span>
                  {/* Batch U2: the edition, after the shelf. */}
                  {editions && <span className="min-w-0 truncate font-normal text-muted-foreground" title={editions}>· {editions}</span>}
                </span>
              </span>
              {movie.copyCount > 1 && <span className="hidden items-center gap-1 text-xs text-muted-foreground md:inline-flex"><Copy className="h-3.5 w-3.5" aria-hidden />{movie.copyCount}</span>}
              {movie.bestFormatOwned && <FormatBadge format={movie.bestFormatOwned} className="shrink-0" />}
              {movie.tmdbRating != null && <span className="hidden w-8 shrink-0 text-right text-xs font-semibold tabular-nums text-warning lg:block">{movie.tmdbRating.toFixed(1)}</span>}
            </Link>
          )
        })}
      </div>
    </div>
  )
}
