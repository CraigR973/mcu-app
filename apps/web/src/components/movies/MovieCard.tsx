import { posterUrl, type MovieListItem } from '@/lib/api'

const FORMAT_BADGE: Record<string, string> = {
  '4K UHD': 'bg-blue-600 text-white',
  'Blu-ray': 'bg-indigo-600 text-white',
  'DVD': 'bg-slate-500 text-white',
}

interface Props {
  movie: MovieListItem
}

export function MovieCard({ movie }: Props) {
  const year = movie.release_date ? new Date(movie.release_date).getFullYear() : null
  const badgeClass = movie.best_format_owned
    ? (FORMAT_BADGE[movie.best_format_owned] ?? 'bg-slate-400 text-white')
    : null

  return (
    <div className="group cursor-pointer rounded-lg overflow-hidden bg-card border border-border hover:border-primary transition-colors duration-200">
      <div className="aspect-[2/3] relative overflow-hidden bg-muted">
        <img
          src={posterUrl(movie.poster_path)}
          alt={movie.title}
          loading="lazy"
          decoding="async"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          onError={(e) => {
            e.currentTarget.src = '/placeholder-poster.svg'
          }}
        />
        {badgeClass && movie.best_format_owned && (
          <span
            className={`absolute top-1.5 right-1.5 text-[9px] font-bold tracking-wide px-1.5 py-0.5 rounded ${badgeClass}`}
          >
            {movie.best_format_owned}
          </span>
        )}
      </div>
      <div className="p-2">
        <p className="text-xs font-medium text-foreground line-clamp-2 leading-snug">{movie.title}</p>
        {year && <p className="text-[10px] text-muted-foreground mt-0.5">{year}</p>}
      </div>
    </div>
  )
}
