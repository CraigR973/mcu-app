import { useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { MovieListItem, FORMAT_COLORS, formatLabel } from '../../lib/api'

interface Props {
  movies: MovieListItem[]
  isLoading: boolean
}

export function MovieCompactView({ movies, isLoading }: Props) {
  const parentRef = useRef<HTMLDivElement>(null)

  const rowVirtualizer = useVirtualizer({
    count: isLoading ? 30 : movies.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 12,
  })

  return (
    <div ref={parentRef} className="overflow-y-auto flex-1">
      <div style={{ height: rowVirtualizer.getTotalSize(), position: 'relative' }}>
        {rowVirtualizer.getVirtualItems().map(vRow => {
          if (isLoading) {
            return (
              <div
                key={vRow.index}
                style={{ position: 'absolute', top: vRow.start, left: 0, right: 0, height: 36 }}
                className="flex items-center gap-3 px-3 border-b border-zinc-800/60"
              >
                <div className="w-4 h-3 rounded bg-zinc-700 animate-pulse shrink-0" />
                <div className="flex-1 h-3 rounded bg-zinc-700 animate-pulse" />
                <div className="w-16 h-3 rounded bg-zinc-700 animate-pulse shrink-0" />
              </div>
            )
          }

          const movie = movies[vRow.index]
          const fmt = movie.best_format_owned

          return (
            <div
              key={movie.id}
              style={{ position: 'absolute', top: vRow.start, left: 0, right: 0, height: 36 }}
              className="flex items-center gap-3 px-3 border-b border-zinc-800/60 hover:bg-zinc-800/40 transition-colors"
            >
              <span className="text-xs text-zinc-600 w-4 shrink-0 text-right">
                {vRow.index + 1}
              </span>
              <p className="flex-1 min-w-0 text-sm text-zinc-200 truncate">{movie.title}</p>
              <span className="text-xs text-zinc-500 shrink-0 w-8 text-right">
                {movie.release_date?.slice(0, 4) ?? ''}
              </span>
              {fmt ? (
                <span className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${FORMAT_COLORS[fmt] ?? 'bg-zinc-700 text-zinc-300'}`}>
                  {formatLabel(fmt)}
                </span>
              ) : (
                <span className="w-14 shrink-0" />
              )}
              {movie.vote_average ? (
                <span className="text-xs text-amber-400 w-8 shrink-0 text-right">
                  {movie.vote_average.toFixed(1)}
                </span>
              ) : (
                <span className="w-8 shrink-0" />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
