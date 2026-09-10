import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { MovieCard } from './MovieCard'
import { SkeletonCard } from './SkeletonCard'
import type { MovieListItem } from '@/lib/api'
import { StatePanel } from '@/components/ui/state-panel'

const CARD_MIN_WIDTH = 152
const GAP = 16
const PADDING_X = 32 // px-4 * 2

interface Props {
  movies: MovieListItem[]
  isLoading: boolean
}

export function MovieGrid({ movies, isLoading }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [columns, setColumns] = useState(4)
  const containerWidthRef = useRef(640)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width
      containerWidthRef.current = w
      const cols = Math.max(2, Math.floor((w - PADDING_X + GAP) / (CARD_MIN_WIDTH + GAP)))
      setColumns(cols)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const items: (MovieListItem | null)[] = isLoading ? Array(24).fill(null) : movies

  const rows = useMemo<(MovieListItem | null)[][]>(() => {
    const result: (MovieListItem | null)[][] = []
    for (let i = 0; i < items.length; i += columns) {
      result.push(items.slice(i, i + columns))
    }
    return result
  }, [items, columns])

  const estimateSize = useCallback(() => {
    const w = containerWidthRef.current
    const cardWidth = (w - PADDING_X - (columns - 1) * GAP) / columns
    // 2:3 artwork plus its title, location and catalogue metadata.
    return Math.round(cardWidth * 1.5 + 86 + GAP)
  }, [columns])

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize,
    overscan: 4,
    measureElement: (el) => el.getBoundingClientRect().height,
  })

  // Re-measure all rows when columns change
  useEffect(() => {
    virtualizer.measure()
  }, [columns]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!isLoading && movies.length === 0) {
    return (
      <StatePanel
        tone="empty"
        title="No films match this view"
        description="Remove one or more filters to widen the archive selection."
        className="m-4 flex-1"
      />
    )
  }

  return (
    <div
      ref={containerRef}
      className="min-h-0 flex-1 overflow-y-auto"
      style={{ contain: 'strict' }}
    >
      <div style={{ height: virtualizer.getTotalSize() + 96, position: 'relative' }}>
        {virtualizer.getVirtualItems().map((vRow) => (
          <div
            key={vRow.key}
            data-index={vRow.index}
            ref={virtualizer.measureElement}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              transform: `translateY(${vRow.start}px)`,
            }}
          >
            <div
              className="grid px-4 pt-4"
              style={{
                gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
                gap: GAP,
              }}
            >
              {rows[vRow.index].map((movie, i) =>
                movie ? (
                  <MovieCard key={movie.id} movie={movie} />
                ) : (
                  <SkeletonCard key={i} />
                ),
              )}
            </div>
          </div>
        ))}
        {/* Bottom padding */}
        {rows.length > 0 && (
          <div style={{ position: 'absolute', bottom: 0, height: 12, left: 0 }} />
        )}
      </div>
    </div>
  )
}
