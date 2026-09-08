import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Settings2 } from 'lucide-react'
import { FORMAT_COLORS, formatLabel, posterUrl, type MovieListItem } from '../../lib/api'
import { ALL_COLUMNS, type ColumnKey } from '../../hooks/useViewPreference'

function formatRuntime(mins: number | null) {
  if (!mins) return '—'
  return `${Math.floor(mins / 60)}h ${mins % 60}m`
}

interface Props {
  movies: MovieListItem[]
  isLoading: boolean
  enabledColumns: ColumnKey[]
  toggleColumn: (key: ColumnKey) => void
}

export function MovieListView({ movies, isLoading, enabledColumns, toggleColumn }: Props) {
  const navigate = useNavigate()
  const parentRef = useRef<HTMLDivElement>(null)
  const [pickerOpen, setPickerOpen] = useState(false)

  const rowVirtualizer = useVirtualizer({
    count: isLoading ? 20 : movies.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 52,
    overscan: 8,
  })

  const colDefs = ALL_COLUMNS.filter(c => enabledColumns.includes(c.key))

  const renderCell = (movie: MovieListItem, key: ColumnKey) => {
    switch (key) {
      case 'year':
        return <span className="text-muted-foreground">{movie.year ?? '—'}</span>
      case 'format': {
        const fmt = movie.bestFormatOwned
        if (!fmt) return <span className="text-zinc-600">—</span>
        return (
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${FORMAT_COLORS[fmt] ?? 'bg-zinc-700 text-zinc-300'}`}>
            {formatLabel(fmt)}
          </span>
        )
      }
      case 'hdr':
        return <span className="text-muted-foreground text-xs">{movie.bestHdrOwned ?? '—'}</span>
      case 'audio':
        return <span className="text-muted-foreground text-xs">{movie.bestAudioOwned ?? '—'}</span>
      case 'runtime':
        return <span className="text-muted-foreground">{formatRuntime(movie.runtimeMinutes)}</span>
      case 'rating':
        return movie.tmdbRating
          ? <span className="text-amber-500 font-medium">{movie.tmdbRating.toFixed(1)}</span>
          : <span className="text-muted-foreground">—</span>
      case 'location': {
        if (movie.locations.length === 0) return <span className="text-muted-foreground">—</span>
        const labels = movie.locations.map(l => l.label).join(' · ')
        return (
          <span className="text-muted-foreground text-xs truncate block" title={labels}>
            {labels}
          </span>
        )
      }
      case 'watched':
        return movie.watched
          ? <span className="text-emerald-500 text-xs font-medium">Watched</span>
          : <span className="text-muted-foreground">—</span>
    }
  }

  return (
    <div className="flex flex-col min-h-0 flex-1">
      {/* Header row */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-zinc-700 bg-zinc-900 text-xs font-medium text-zinc-500 uppercase tracking-wide select-none">
        <div className="w-8 shrink-0" />
        <div className="flex-1 min-w-0">Title</div>
        {colDefs.map(c => (
          <div key={c.key} className="w-16 shrink-0 text-right">{c.label}</div>
        ))}
        <div className="relative ml-auto shrink-0">
          <button
            onClick={() => setPickerOpen(p => !p)}
            title="Configure columns"
            className="p-1 rounded hover:bg-zinc-700 text-zinc-500 hover:text-zinc-200 transition-colors"
          >
            <Settings2 size={15} />
          </button>
          {pickerOpen && (
            <div className="absolute right-0 top-7 z-20 w-44 rounded-lg border border-zinc-700 bg-zinc-850 shadow-xl p-2 bg-zinc-900">
              <p className="text-xs text-zinc-500 px-1 pb-1 font-semibold uppercase tracking-wide">Columns</p>
              {ALL_COLUMNS.map(c => (
                <label key={c.key} className="flex items-center gap-2 px-1 py-1 rounded hover:bg-zinc-700 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enabledColumns.includes(c.key)}
                    onChange={() => toggleColumn(c.key)}
                    className="accent-blue-500"
                  />
                  <span className="text-sm text-zinc-300">{c.label}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Virtual rows */}
      <div ref={parentRef} className="overflow-y-auto flex-1">
        <div style={{ height: rowVirtualizer.getTotalSize(), position: 'relative' }}>
          {rowVirtualizer.getVirtualItems().map(vRow => {
            if (isLoading) {
              return (
                <div
                  key={vRow.index}
                  style={{ position: 'absolute', top: vRow.start, left: 0, right: 0, height: 52 }}
                  className="flex items-center gap-2 px-3 border-b border-zinc-800"
                >
                  <div className="w-8 h-10 rounded bg-zinc-700 animate-pulse shrink-0" />
                  <div className="flex-1 h-4 rounded bg-zinc-700 animate-pulse" />
                  {colDefs.map(c => (
                    <div key={c.key} className="w-24 h-4 rounded bg-zinc-700 animate-pulse shrink-0" />
                  ))}
                </div>
              )
            }

            const movie = movies[vRow.index]
            return (
              <div
                key={movie.id}
                style={{ position: 'absolute', top: vRow.start, left: 0, right: 0, height: 52 }}
                className="flex items-center gap-2 px-3 border-b border-zinc-800 hover:bg-zinc-800/50 transition-colors cursor-pointer"
                onClick={() => navigate(`/movies/${movie.id}`)}
              >
                <div className="w-8 h-10 shrink-0 rounded overflow-hidden bg-zinc-800">
                  {movie.posterPath && (
                    <img
                      src={posterUrl(movie.posterPath, 'w92')}
                      alt=""
                      loading="lazy"
                      decoding="async"
                      className="w-full h-full object-cover"
                    />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-zinc-100 truncate">{movie.title}</p>
                  {!movie.identified && (
                    <p className="text-[10px] font-medium text-amber-500">Needs identification</p>
                  )}
                </div>
                {colDefs.map(c => (
                  <div key={c.key} className="w-24 shrink-0 text-right text-sm">
                    {renderCell(movie, c.key)}
                  </div>
                ))}
                <div className="w-[23px] shrink-0" /> {/* spacer for settings gear */}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
