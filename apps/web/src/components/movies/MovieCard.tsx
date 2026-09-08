import { memo } from 'react'
import { Link } from 'react-router-dom'
import { CircleHelp, Copy } from 'lucide-react'

import { FORMAT_COLORS, formatLabel, posterUrl, type MovieListItem } from '@/lib/api'

interface Props {
  movie: MovieListItem
}

export const MovieCard = memo(function MovieCard({ movie }: Props) {
  const badgeClass = movie.bestFormatOwned
    ? (FORMAT_COLORS[movie.bestFormatOwned] ?? 'bg-slate-500 text-white')
    : null

  return (
    <Link to={`/movies/${movie.id}`} className="group cursor-pointer rounded-lg overflow-hidden bg-card border border-border hover:border-primary transition-colors duration-200 block">
      <div className="aspect-[2/3] relative overflow-hidden bg-muted">
        <img
          src={posterUrl(movie.posterPath)}
          alt={movie.title}
          loading="lazy"
          decoding="async"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          onError={(e) => {
            e.currentTarget.src = '/placeholder-poster.svg'
          }}
        />
        {badgeClass && movie.bestFormatOwned && (
          <span
            className={`absolute top-1.5 right-1.5 text-[9px] font-bold tracking-wide px-1.5 py-0.5 rounded ${badgeClass}`}
          >
            {formatLabel(movie.bestFormatOwned)}
          </span>
        )}
        {!movie.identified && (
          <span className="absolute bottom-1.5 left-1.5 inline-flex items-center gap-1 rounded bg-amber-400 px-1.5 py-0.5 text-[10px] font-bold text-zinc-950 shadow">
            <CircleHelp className="h-3 w-3" /> Identify
          </span>
        )}
      </div>
      <div className="p-2">
        <p className="text-xs font-medium text-foreground line-clamp-2 leading-snug">{movie.title}</p>
        <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
          <span>{movie.year ?? 'Unknown year'}</span>
          {movie.copyCount > 1 && (
            <span className="inline-flex items-center gap-0.5" aria-label={`${movie.copyCount} copies`}>
              <Copy className="h-2.5 w-2.5" /> {movie.copyCount}
            </span>
          )}
        </div>
      </div>
    </Link>
  )
})
