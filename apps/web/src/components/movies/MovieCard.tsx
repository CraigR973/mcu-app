import { memo } from 'react'
import { Link } from 'react-router-dom'
import { CircleHelp, Copy, Eye, MapPin } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { type MovieListItem } from '@/lib/api'
import { FormatBadge } from './FormatBadge'
import { Poster } from './Poster'

interface Props {
  movie: MovieListItem
}

export const MovieCard = memo(function MovieCard({ movie }: Props) {
  return (
    <Link
      to={`/movies/${movie.id}`}
      className="group block overflow-hidden rounded-md border border-border bg-card transition-colors hover:border-primary/70 hover:bg-surface-raised"
      aria-label={`${movie.title}${movie.year ? ` (${movie.year})` : ''}${movie.bestFormatOwned ? `, owned on ${movie.bestFormatOwned.replaceAll('_', ' ')}` : ''}`}
    >
      <div className="relative aspect-[2/3] overflow-hidden bg-muted">
        <Poster path={movie.posterPath} title={movie.title} decorative className="h-full w-full transition-transform duration-300 group-hover:scale-[1.025]" />
        <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-brand-ink/70 to-transparent" aria-hidden />
        {movie.bestFormatOwned && (
          <FormatBadge format={movie.bestFormatOwned} className="absolute right-2 top-2 bg-popover/95 shadow-soft" />
        )}
        {!movie.identified && (
          <Badge tone="warning" className="absolute bottom-2 left-2 bg-popover/95">
            <CircleHelp className="mr-1 h-3.5 w-3.5" aria-hidden /> Identify
          </Badge>
        )}
        {movie.watched && (
          <span
            className="absolute left-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-full bg-success text-success-foreground shadow-soft"
            aria-label="Watched"
            title="Watched"
          >
            <Eye className="h-3.5 w-3.5" aria-hidden />
          </span>
        )}
      </div>
      <div className="p-2.5 sm:p-3">
        <p className="line-clamp-2 min-h-9 font-display text-sm font-semibold leading-[1.25] text-foreground">{movie.title}</p>
        <div className="mt-1.5 flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <span>{movie.year ?? 'Unknown year'}</span>
          {movie.copyCount > 1 && (
            <span className="inline-flex items-center gap-0.5" aria-label={`${movie.copyCount} copies`}>
              <Copy className="h-3.5 w-3.5" aria-hidden /> {movie.copyCount}
            </span>
          )}
        </div>
        {/* §6.2: a result is meant to tell you where the disc actually is. */}
        {movie.locations.length > 0 && (
          <p
            className="mt-1 flex items-center gap-1 truncate text-xs font-medium text-foreground"
            title={movie.locations.map((l) => l.label).join(' · ')}
          >
            <MapPin className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden />
            {movie.locations.map((l) => l.label).join(' · ')}
          </p>
        )}
        {/* Batch U2: which edition is on the shelf, for a film whose copies record one. */}
        {movie.editions.length > 0 && (
          <p className="mt-0.5 truncate text-xs text-muted-foreground" title={movie.editions.join(' · ')}>
            {movie.editions.join(' · ')}
          </p>
        )}
      </div>
    </Link>
  )
})
