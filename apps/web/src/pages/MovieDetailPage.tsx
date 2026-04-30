import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Star, Clock, ExternalLink, Disc3, Package } from 'lucide-react'
import {
  fetchMovie,
  fetchCopies,
  backdropUrl,
  posterUrl,
  formatLabel,
  FORMAT_COLORS,
  CollectionItemOut,
} from '@/lib/api'

type Tab = 'overview' | 'crew' | 'copies'

const CONDITION_LABELS: Record<string, string> = {
  sealed: 'Sealed',
  mint: 'Mint',
  very_good: 'Very Good',
  good: 'Good',
  fair: 'Fair',
  poor: 'Poor',
}

function CopyCard({ item }: { item: CollectionItemOut }) {
  const fmtLabel = formatLabel(item.format)
  const fmtColor = FORMAT_COLORS[item.format] ?? 'bg-slate-700 text-slate-300'

  return (
    <div className="rounded-lg border border-border bg-card p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs px-2 py-0.5 rounded font-medium ${fmtColor}`}>
            {fmtLabel ?? item.format}
          </span>
          {item.edition && (
            <span className="text-xs px-2 py-0.5 rounded bg-muted text-muted-foreground">
              {item.edition}
            </span>
          )}
        </div>
        <span className="text-xs text-muted-foreground shrink-0">
          {CONDITION_LABELS[item.condition] ?? item.condition}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {item.region && (
          <span><span className="text-foreground/60">Region</span> {item.region}</span>
        )}
        {item.hdr_format && (
          <span><span className="text-foreground/60">HDR</span> {item.hdr_format}</span>
        )}
        {item.resolution && (
          <span><span className="text-foreground/60">Res</span> {item.resolution}</span>
        )}
        {item.audio_formats && item.audio_formats.length > 0 && (
          <span className="col-span-2">
            <span className="text-foreground/60">Audio</span> {item.audio_formats.join(', ')}
          </span>
        )}
        {item.purchase_source && (
          <span><span className="text-foreground/60">From</span> {item.purchase_source}</span>
        )}
        {item.purchase_date && (
          <span><span className="text-foreground/60">Date</span> {item.purchase_date}</span>
        )}
        {item.purchase_price && (
          <span><span className="text-foreground/60">Paid</span> £{item.purchase_price}</span>
        )}
      </div>

      {item.notes && (
        <p className="text-xs text-muted-foreground italic border-t border-border pt-2">
          {item.notes}
        </p>
      )}

      {item.is_for_sale && (
        <span className="inline-block text-xs px-2 py-0.5 rounded bg-green-900 text-green-300">
          For sale
        </span>
      )}
    </div>
  )
}

export default function MovieDetailPage() {
  const { id } = useParams<{ id: string }>()
  const movieId = Number(id)
  const [tab, setTab] = useState<Tab>('overview')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['movie', movieId],
    queryFn: () => fetchMovie(movieId),
    enabled: !isNaN(movieId),
  })

  const { data: copies = [] } = useQuery({
    queryKey: ['movie-copies', movieId],
    queryFn: () => fetchCopies(movieId),
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

  const TABS: { key: Tab; label: string; count?: number }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'crew', label: 'Crew', count: movie.crew.length },
    { key: 'copies', label: 'Your Copies', count: copies.length },
  ]

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

        {/* Tab bar */}
        <div className="mt-8 flex gap-1 border-b border-border">
          {TABS.map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
                tab === key
                  ? 'border-primary text-foreground'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {label}
              {count !== undefined && count > 0 && (
                <span className="ml-1.5 text-xs rounded-full bg-muted px-1.5 py-0.5">
                  {count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab: Overview */}
        {tab === 'overview' && (
          <div className="mt-6 space-y-8">
            {movie.overview && (
              <div className="max-w-3xl">
                <p className="text-sm text-muted-foreground leading-relaxed">{movie.overview}</p>
              </div>
            )}

            {movie.cast.length > 0 && (
              <div>
                <h2 className="text-base font-semibold text-foreground mb-3">Cast</h2>
                <div className="flex gap-3 overflow-x-auto pb-2">
                  {movie.cast.map((c, i) => (
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
        )}

        {/* Tab: Crew */}
        {tab === 'crew' && (
          <div className="mt-6">
            {movie.crew.length === 0 ? (
              <p className="text-sm text-muted-foreground">No crew data available.</p>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 max-w-3xl">
                {movie.crew.map((c, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full overflow-hidden bg-muted shrink-0">
                      {c.profile_path ? (
                        <img
                          src={`https://image.tmdb.org/t/p/w185${c.profile_path}`}
                          alt={c.person_name ?? ''}
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-sm font-medium text-muted-foreground">
                          {c.person_name?.charAt(0) ?? '?'}
                        </div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground leading-tight truncate">
                        {c.person_name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">
                        {c.job ?? c.department}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab: Your Copies */}
        {tab === 'copies' && (
          <div className="mt-6">
            {copies.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center gap-3">
                <Package className="h-10 w-10 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">No copies in your collection.</p>
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <Disc3 className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    {copies.length} {copies.length === 1 ? 'copy' : 'copies'}
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 max-w-3xl">
                  {copies.map((item) => (
                    <CopyCard key={item.id} item={item} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
