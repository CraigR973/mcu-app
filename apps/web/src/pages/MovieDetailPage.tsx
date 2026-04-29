import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Star, Clock, ExternalLink } from 'lucide-react'
import { fetchMovie, backdropUrl, posterUrl, formatLabel, FORMAT_COLORS } from '@/lib/api'

export default function MovieDetailPage() {
  const { id } = useParams<{ id: string }>()
  const movieId = Number(id)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['movie', movieId],
    queryFn: () => fetchMovie(movieId),
    enabled: !isNaN(movieId),
  })

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (isError || !data) {
    return (
      <div className="p-6">
        <p className="text-destructive">Failed to load movie.</p>
        <Link to="/movies" className="mt-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to movies
        </Link>
      </div>
    )
  }

  const movie = data.data
  const year = movie.release_date ? new Date(movie.release_date).getFullYear() : null
  const runtime = movie.runtime
    ? `${Math.floor(movie.runtime / 60)}h ${movie.runtime % 60}m`
    : null
  const rating = movie.vote_average ? movie.vote_average.toFixed(1) : null
  const fmtLabel = formatLabel(movie.best_format_owned)
  const fmtColor = movie.best_format_owned ? (FORMAT_COLORS[movie.best_format_owned] ?? '') : ''
  const backdrop = backdropUrl(movie.backdrop_path)
  const imdbUrl = movie.imdb_id ? `https://www.imdb.com/title/${movie.imdb_id}/` : null
  const letterboxdUrl = `https://letterboxd.com/search/${encodeURIComponent(movie.title)}/`

  return (
    <div className="min-h-full">
      {/* Hero */}
      <div className="relative h-[280px] md:h-[380px] overflow-hidden bg-zinc-900">
        {backdrop && (
          <img
            src={backdrop}
            alt=""
            className="absolute inset-0 w-full h-full object-cover object-center opacity-50"
          />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/50 to-transparent" />
        <div className="absolute top-4 left-4">
          <Link
            to="/movies"
            className="flex items-center gap-1.5 rounded-md bg-black/40 px-3 py-1.5 text-sm text-white/90 backdrop-blur-sm hover:bg-black/60 hover:text-white transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
        </div>
      </div>

      {/* Content — overlaps hero via negative margin */}
      <div className="relative px-4 md:px-8 pb-12 -mt-28">
        <div className="flex gap-5 items-end">
          {/* Poster */}
          <div className="hidden sm:block shrink-0 w-28 md:w-40 rounded-lg overflow-hidden border border-border shadow-2xl">
            <img
              src={posterUrl(movie.poster_path, 'w342')}
              alt={movie.title}
              className="w-full aspect-[2/3] object-cover"
              onError={(e) => { e.currentTarget.src = '/placeholder-poster.svg' }}
            />
          </div>

          {/* Title block */}
          <div className="flex-1 min-w-0 pb-1">
            {movie.tagline && (
              <p className="text-sm text-muted-foreground italic mb-1 drop-shadow">{movie.tagline}</p>
            )}
            <h1 className="text-2xl md:text-4xl font-bold text-foreground leading-tight drop-shadow-md">
              {movie.title}
            </h1>

            {/* Metadata row */}
            <div className="flex flex-wrap items-center gap-3 mt-2.5 text-sm text-muted-foreground">
              {year && <span>{year}</span>}
              {runtime && (
                <span className="flex items-center gap-1">
                  <Clock className="h-3.5 w-3.5" />
                  {runtime}
                </span>
              )}
              {rating && (
                <span className="flex items-center gap-1">
                  <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />
                  {rating}
                </span>
              )}
              {fmtLabel && (
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${fmtColor}`}>
                  {fmtLabel}
                </span>
              )}
            </div>

            {/* External links */}
            <div className="flex gap-2.5 mt-4">
              {imdbUrl && (
                <a
                  href={imdbUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-md bg-yellow-500 px-3 py-1.5 text-xs font-bold text-black hover:bg-yellow-400 transition-colors"
                >
                  IMDb <ExternalLink className="h-3 w-3" />
                </a>
              )}
              <a
                href={letterboxdUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md bg-[#00b020] px-3 py-1.5 text-xs font-bold text-white hover:bg-[#00c824] transition-colors"
              >
                Letterboxd <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        </div>

        {/* Overview */}
        {movie.overview && (
          <div className="mt-8 max-w-3xl">
            <h2 className="text-base font-semibold text-foreground mb-2">Overview</h2>
            <p className="text-sm text-muted-foreground leading-relaxed">{movie.overview}</p>
          </div>
        )}

        {/* Cast */}
        {movie.cast.length > 0 && (
          <div className="mt-8">
            <h2 className="text-base font-semibold text-foreground mb-3">Cast</h2>
            <div className="flex gap-3 overflow-x-auto pb-2">
              {movie.cast.slice(0, 12).map((c, i) => (
                <div key={i} className="shrink-0 w-20 text-center">
                  <div className="w-20 h-20 rounded-full overflow-hidden bg-muted mx-auto">
                    {c.profile_path ? (
                      <img
                        src={`https://image.tmdb.org/t/p/w185${c.profile_path}`}
                        alt={c.person_name ?? ''}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-xl font-medium text-muted-foreground">
                        {c.person_name?.charAt(0) ?? '?'}
                      </div>
                    )}
                  </div>
                  <p className="text-xs font-medium text-foreground mt-1.5 leading-tight line-clamp-2">
                    {c.person_name}
                  </p>
                  {c.character && (
                    <p className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1">{c.character}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
