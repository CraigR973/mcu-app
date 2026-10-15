import { useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Check, MapPin, Settings2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { StatePanel } from '@/components/ui/state-panel'
import { isIdentifiedSeries, needsIdentifying, type MovieListItem } from '@/lib/api'
import { ALL_COLUMNS, type ColumnKey } from '@/hooks/useViewPreference'
import { FormatBadge } from './FormatBadge'
import { Poster } from './Poster'

function formatRuntime(minutes: number | null) {
  if (!minutes) return '—'
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

interface Props {
  movies: MovieListItem[]
  isLoading: boolean
  enabledColumns: ColumnKey[]
  toggleColumn: (key: ColumnKey) => void
}

export function MovieListView({ movies, isLoading, enabledColumns, toggleColumn }: Props) {
  const parentRef = useRef<HTMLDivElement>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const rowHeight = 68

  const rowVirtualizer = useVirtualizer({
    count: isLoading ? 20 : movies.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 8,
  })
  const colDefs = ALL_COLUMNS.filter((column) => enabledColumns.includes(column.key))

  function renderCell(movie: MovieListItem, key: ColumnKey) {
    switch (key) {
      case 'year': return <span className="text-muted-foreground">{movie.year ?? '—'}</span>
      case 'format': return movie.bestFormatOwned ? <FormatBadge format={movie.bestFormatOwned} /> : <span className="text-muted-foreground">—</span>
      case 'hdr': return <span className="block truncate text-xs text-muted-foreground">{movie.bestHdrOwned ?? '—'}</span>
      case 'audio': return <span className="block truncate text-xs text-muted-foreground">{movie.bestAudioOwned ?? '—'}</span>
      case 'runtime': return <span className="text-muted-foreground">{formatRuntime(movie.runtimeMinutes)}</span>
      case 'rating': return movie.tmdbRating ? <span className="font-semibold tabular-nums text-warning">{movie.tmdbRating.toFixed(1)}</span> : <span className="text-muted-foreground">—</span>
      case 'location': {
        const locations = movie.locations.map((location) => location.label).join(' · ')
        return <span className="block truncate text-xs font-medium text-foreground" title={locations}>{locations || '—'}</span>
      }
      case 'watched': return movie.watched ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-success"><Check className="h-3.5 w-3.5" aria-hidden /> Seen</span> : <span className="text-muted-foreground">—</span>
    }
  }

  if (!isLoading && movies.length === 0) {
    return <StatePanel tone="empty" title="No films match this view" description="Remove one or more filters to widen the archive selection." className="m-4 flex-1" />
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="relative hidden min-h-11 items-center gap-3 border-b border-border bg-surface-sunken/65 px-4 text-[0.6875rem] font-semibold uppercase tracking-[0.13em] text-muted-foreground lg:flex">
        <div className="w-9 shrink-0" />
        <div className="min-w-0 flex-1">Film</div>
        {colDefs.map((column) => <div key={column.key} className="w-24 shrink-0 text-right">{column.label}</div>)}
        <button type="button" onClick={() => setPickerOpen((value) => !value)} aria-expanded={pickerOpen} aria-label="Configure visible columns" className="touch-target flex shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground">
          <Settings2 size={17} aria-hidden />
        </button>
        {pickerOpen && (
          <div className="absolute right-3 top-11 z-20 w-52 rounded-lg border border-border bg-popover p-2 normal-case tracking-normal shadow-lift">
            <p className="px-2 pb-1 text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Visible columns</p>
            {ALL_COLUMNS.map((column) => (
              <label key={column.key} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-2 text-sm font-medium text-foreground hover:bg-muted">
                <input type="checkbox" checked={enabledColumns.includes(column.key)} onChange={() => toggleColumn(column.key)} className="h-4 w-4 accent-primary" />
                {column.label}
              </label>
            ))}
          </div>
        )}
      </div>

      <div ref={parentRef} className="min-h-0 flex-1 overflow-y-auto" aria-busy={isLoading}>
        <div style={{ height: rowVirtualizer.getTotalSize() + 96, position: 'relative' }}>
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const positioning = { position: 'absolute' as const, top: virtualRow.start, left: 0, right: 0, height: rowHeight }
            if (isLoading) {
              return (
                <div key={virtualRow.index} style={positioning} className="flex items-center gap-3 border-b border-border px-4">
                  <div className="h-12 w-8 shrink-0 animate-pulse rounded-sm bg-muted" />
                  <div className="h-4 flex-1 animate-pulse rounded-sm bg-muted" />
                  {colDefs.map((column) => <div key={column.key} className="hidden h-4 w-24 shrink-0 animate-pulse rounded-sm bg-muted lg:block" />)}
                  <div className="hidden w-11 lg:block" />
                </div>
              )
            }

            const movie = movies[virtualRow.index]
            const locations = movie.locations.map((location) => location.label).join(' · ')
            const editions = movie.editions.join(' · ')
            return (
              <Link key={movie.id} to={`/movies/${movie.id}`} style={positioning} className="group flex items-center gap-3 border-b border-border px-4 transition-colors hover:bg-muted/70 focus-visible:z-10">
                <Poster path={movie.posterPath} title={movie.title} size="w92" decorative className="h-12 w-8 shrink-0 rounded-sm" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-foreground">{movie.title}</span>
                  <span className="mt-1 flex min-w-0 items-center gap-2 text-xs text-muted-foreground lg:hidden">
                    {movie.bestFormatOwned && <FormatBadge format={movie.bestFormatOwned} />}
                    <span className="inline-flex min-w-0 items-center gap-1 truncate font-medium text-foreground"><MapPin className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />{locations || 'Location not recorded'}</span>
                    {/* Batch U2: the edition, after the shelf, on a phone. */}
                    {editions && <span className="min-w-0 shrink truncate" title={editions}>{editions}</span>}
                  </span>
                  {editions && <span className="mt-0.5 hidden truncate text-xs text-muted-foreground lg:block" title={editions}>{editions}</span>}
                  {needsIdentifying(movie) && <span className="block text-xs font-semibold text-warning">Needs identification</span>}
                  {isIdentifiedSeries(movie) && <span className="block text-xs text-muted-foreground">TV series</span>}
                </span>
                {colDefs.map((column) => <span key={column.key} className="hidden w-24 shrink-0 text-right text-sm lg:block">{renderCell(movie, column.key)}</span>)}
                <span className="hidden w-11 shrink-0 lg:block" aria-hidden />
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}
