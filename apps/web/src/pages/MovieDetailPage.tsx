import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  Clock,
  Disc3,
  ExternalLink,
  Loader2,
  MapPin,
  Package,
  Pencil,
  Plus,
  RefreshCcw,
  ShieldAlert,
  Star,
} from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import CopyEditor, { fieldsFrom } from '@/components/collection/CopyEditor'
import { LendButton } from '@/components/collection/LendButton'
import { RecommendationsPanel } from '@/components/movies/RecommendationsPanel'
import { StreamingPanel } from '@/components/movies/StreamingPanel'
import ItemHistory from '@/components/collection/ItemHistory'
import IdentifyPanel from '@/components/movies/IdentifyPanel'
import WatchPanel from '@/components/movies/WatchPanel'
import { useAuth } from '@/context/auth'
import {
  backdropUrl,
  conditionLabel,
  fetchCopies,
  fetchMovie,
  FORMAT_COLORS,
  formatLabel,
  posterUrl,
  updateCollectionItem,
  type CollectionCopy,
  type MovieDetail,
} from '@/lib/api'

type Tab = 'overview' | 'crew' | 'copies' | 'watch'

function CopyCard({
  item,
  movieId,
  canEdit,
  onEdit,
}: {
  item: CollectionCopy
  movieId: string
  canEdit: boolean
  onEdit: (copy: CollectionCopy) => void
}) {
  const queryClient = useQueryClient()

  // §3.11's "mark as damaged" quick action. It is the ordinary update with one field
  // changed — the client already holds the whole copy — so there is only one path that
  // has to remember to stamp `conditionUpdatedAt` and write the audit row.
  const markDamaged = useMutation({
    mutationFn: () =>
      updateCollectionItem(item.id, {
        ...fieldsFrom(item),
        condition: 'damaged',
        hasPlaybackIssues: true,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['movie-copies', movieId] })
      void queryClient.invalidateQueries({ queryKey: ['item-history', movieId] })
    },
  })

  return (
    <article className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {item.formats.map((format) => (
            <span
              key={format}
              className={`rounded px-2 py-0.5 text-xs font-medium ${FORMAT_COLORS[format] ?? 'bg-secondary text-secondary-foreground'}`}
            >
              {formatLabel(format)}
            </span>
          ))}
        </div>
        {item.condition && (
          <span className="text-xs text-muted-foreground">{conditionLabel(item.condition)}</span>
        )}
      </div>

      {item.location && (
        <div className="flex items-start gap-2 rounded-lg bg-primary/10 px-3 py-2 text-sm">
          <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <div>
            <p className="font-medium text-foreground">{item.location}</p>
            {item.section && (
              <p className="text-xs text-muted-foreground">
                {item.section}{item.shelf ? ` · ${item.shelf} shelf` : ''}
              </p>
            )}
          </div>
        </div>
      )}

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {item.regionCode && <><dt>Region</dt><dd className="text-right">{item.regionCode}</dd></>}
        {item.releaseLabel && <><dt>Label</dt><dd className="text-right">{item.releaseLabel}</dd></>}
        {item.purchaseSource && <><dt>Bought from</dt><dd className="text-right">{item.purchaseSource}</dd></>}
        {item.purchaseDate && <><dt>Bought</dt><dd className="text-right">{item.purchaseDate}</dd></>}
        {item.purchasePrice && <><dt>Paid</dt><dd className="text-right">£{item.purchasePrice}</dd></>}
      </dl>

      {item.notes && <p className="border-t border-border pt-2 text-xs italic text-muted-foreground">{item.notes}</p>}
      {item.hasPlaybackIssues && (
        <p className="rounded bg-destructive/10 px-2 py-1 text-xs text-destructive">
          Playback issue{item.playbackNotes ? `: ${item.playbackNotes}` : ''}
        </p>
      )}

      {canEdit && (
        <div className="flex flex-wrap gap-2 border-t border-border pt-3">
          <button
            type="button"
            onClick={() => onEdit(item)}
            className="inline-flex items-center gap-1.5 rounded-md bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground"
          >
            <Pencil className="h-3 w-3" /> Edit
          </button>
          {item.condition !== 'damaged' && (
            <button
              type="button"
              onClick={() => markDamaged.mutate()}
              disabled={markDamaged.isPending}
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium text-destructive hover:bg-destructive/10 disabled:opacity-60"
            >
              {markDamaged.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <ShieldAlert className="h-3 w-3" />
              )}
              Mark damaged
            </button>
          )}
        </div>
      )}
      {/* §12.5's "mark as lent / returned", on the copy rather than the film: a loan is
          about one physical object, and owning a film twice means only one of them left
          the house. */}
      {canEdit && (
        <div className="border-t border-border pt-3">
          <LendButton collectionItemId={item.id} />
        </div>
      )}
      {markDamaged.isError && (
        <p className="text-xs text-destructive">
          {markDamaged.error instanceof Error
            ? markDamaged.error.message
            : 'Could not update this disc.'}
        </p>
      )}
    </article>
  )
}

export default function MovieDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('overview')
  const [correcting, setCorrecting] = useState(false)
  const [editing, setEditing] = useState<CollectionCopy | null>(null)
  const { profile } = useAuth()
  const canEdit = profile?.role === 'admin'
  const movieId = id ?? ''

  const movieQuery = useQuery({
    queryKey: ['movie', movieId],
    queryFn: () => fetchMovie(movieId),
    enabled: movieId.length > 0,
  })
  const copiesQuery = useQuery({
    queryKey: ['movie-copies', movieId],
    queryFn: () => fetchCopies(movieId),
    enabled: movieId.length > 0,
  })

  function identified(movie: MovieDetail) {
    queryClient.setQueryData(['movie', movie.id], movie)
    void queryClient.invalidateQueries({ queryKey: ['movies'] })
    void queryClient.invalidateQueries({ queryKey: ['search'] })
    void queryClient.invalidateQueries({ queryKey: ['movie-copies', movie.id] })
    setCorrecting(false)
    if (movie.id !== movieId) navigate(`/movies/${movie.id}`, { replace: true })
  }

  if (movieQuery.isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (movieQuery.isError || !movieQuery.data) {
    return (
      <div className="p-6">
        <p className="text-destructive">
          {movieQuery.error instanceof Error ? movieQuery.error.message : 'Failed to load movie.'}
        </p>
        <Link to="/movies" className="mt-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to movies
        </Link>
      </div>
    )
  }

  const movie = movieQuery.data
  const copies = copiesQuery.data ?? []
  const runtime = movie.runtimeMinutes
    ? `${Math.floor(movie.runtimeMinutes / 60)}h ${movie.runtimeMinutes % 60}m`
    : null
  const rating = movie.tmdbRating ? movie.tmdbRating.toFixed(1) : null
  const format = formatLabel(movie.bestFormatOwned)
  const formatColor = movie.bestFormatOwned
    ? (FORMAT_COLORS[movie.bestFormatOwned] ?? 'bg-secondary text-secondary-foreground')
    : ''
  const backdrop = backdropUrl(movie.backdropPath)
  const imdbUrl = movie.imdbId ? `https://www.imdb.com/title/${movie.imdbId}/` : null
  const letterboxdUrl = movie.letterboxdSlug
    ? `https://letterboxd.com/film/${movie.letterboxdSlug}/`
    : `https://letterboxd.com/search/${encodeURIComponent(movie.title)}/`

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'crew', label: 'Crew', count: movie.crew.length },
    { key: 'copies', label: 'Your copies', count: copies.length },
    // Batch 16 (§7.1, §7.2). One tab, because "where can I watch this" and "what else
    // is like it" are the same question asked twice.
    { key: 'watch', label: 'Where to watch' },
  ]

  return (
    <div className="min-h-full pb-12">
      <div className="relative h-64 overflow-hidden bg-zinc-900 md:h-96">
        {backdrop && (
          <img src={backdrop} alt="" className="absolute inset-0 h-full w-full object-cover opacity-50" />
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-background via-background/45 to-black/20" />
        <Link
          to="/movies"
          className="absolute left-4 top-4 inline-flex items-center gap-1.5 rounded-md bg-black/45 px-3 py-1.5 text-sm text-white backdrop-blur-sm hover:bg-black/65"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
      </div>

      <div className="relative -mt-28 px-4 md:px-8">
        <div className="flex items-end gap-5">
          <div className="hidden w-28 shrink-0 overflow-hidden rounded-xl border border-border bg-muted shadow-2xl sm:block md:w-40">
            <img
              src={posterUrl(movie.posterPath, 'w342')}
              alt={`${movie.title} poster`}
              className="aspect-[2/3] w-full object-cover"
            />
          </div>
          <div className="min-w-0 flex-1 pb-1">
            {movie.tagline && <p className="mb-1 text-sm italic text-muted-foreground">{movie.tagline}</p>}
            <h1 className="text-2xl font-bold leading-tight text-foreground drop-shadow md:text-4xl">{movie.title}</h1>
            <div className="mt-2.5 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              {movie.year && <span>{movie.year}</span>}
              {runtime && <span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" />{runtime}</span>}
              {rating && <span className="inline-flex items-center gap-1"><Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />{rating}</span>}
              {format && <span className={`rounded px-2 py-0.5 text-xs font-medium ${formatColor}`}>{format}</span>}
              <span className="inline-flex items-center gap-1"><Disc3 className="h-3.5 w-3.5" />{movie.copyCount} {movie.copyCount === 1 ? 'copy' : 'copies'}</span>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {imdbUrl && (
                <a href={imdbUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-md bg-yellow-400 px-3 py-1.5 text-xs font-bold text-black">
                  IMDb <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {movie.identified && (
                <a href={letterboxdUrl} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white">
                  Letterboxd <ExternalLink className="h-3 w-3" />
                </a>
              )}
              {movie.identified && (
                <button type="button" onClick={() => setCorrecting((value) => !value)} className="inline-flex items-center gap-1.5 rounded-md bg-secondary px-3 py-1.5 text-xs font-semibold text-secondary-foreground">
                  <RefreshCcw className="h-3 w-3" /> Correct match
                </button>
              )}
            </div>
          </div>
        </div>

        {(!movie.identified || correcting) && (
          <div className="mt-8">
            <IdentifyPanel movieId={movie.id} storedTitle={movie.title} onIdentified={identified} />
          </div>
        )}

        <div className="mt-8 grid gap-4 lg:grid-cols-2">
          <WatchPanel movieId={movie.id} />
          {/* Admin-only: `GET /admin/audit` is, so a viewer would only watch it fail. */}
          {canEdit && <ItemHistory movieId={movie.id} />}
        </div>

        <div className="mt-8 flex gap-1 overflow-x-auto border-b border-border">
          {tabs.map(({ key, label, count }) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2 text-sm font-medium transition-colors ${tab === key ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'}`}
            >
              {label}
              {count !== undefined && count > 0 && <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-xs">{count}</span>}
            </button>
          ))}
        </div>

        {tab === 'overview' && (
          <div className="mt-6 space-y-8">
            {movie.overview ? (
              <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{movie.overview}</p>
            ) : movie.identified ? (
              <p className="text-sm text-muted-foreground">No overview is available for this film.</p>
            ) : (
              <p className="text-sm text-muted-foreground">Choose the film above to add its overview and cast.</p>
            )}

            {movie.cast.length > 0 && (
              <section>
                <h2 className="mb-3 font-semibold text-foreground">Cast</h2>
                <div className="flex gap-3 overflow-x-auto pb-2">
                  {movie.cast.map((member) => (
                    <div key={`${member.tmdbPersonId}-${member.personName}`} className="w-20 shrink-0 text-center">
                      <div className="mx-auto flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-muted text-xl text-muted-foreground">
                        {member.profilePath ? (
                          <img src={`https://image.tmdb.org/t/p/w185${member.profilePath}`} alt="" className="h-full w-full object-cover" loading="lazy" />
                        ) : member.personName.charAt(0)}
                      </div>
                      <p className="mt-1.5 line-clamp-2 text-xs font-medium text-foreground">{member.personName}</p>
                      {member.characterName && <p className="mt-0.5 line-clamp-1 text-[10px] text-muted-foreground">{member.characterName}</p>}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {tab === 'crew' && (
          <div className="mt-6 grid max-w-3xl gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {movie.crew.length === 0 ? (
              <p className="text-sm text-muted-foreground">No crew data available.</p>
            ) : movie.crew.map((member) => (
              <div key={`${member.role}-${member.tmdbPersonId}-${member.personName}`} className="rounded-lg border border-border bg-card px-3 py-2">
                <p className="text-sm font-medium text-foreground">{member.personName}</p>
                <p className="text-xs capitalize text-muted-foreground">{member.role}</p>
              </div>
            ))}
          </div>
        )}

        {tab === 'watch' && (
          <div className="mt-6 max-w-4xl space-y-6">
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-foreground">Streaming</h2>
              <StreamingPanel movieId={movie.id} />
            </section>
            <section className="space-y-2">
              <h2 className="text-sm font-semibold text-foreground">If you liked this</h2>
              <RecommendationsPanel movieId={movie.id} />
            </section>
          </div>
        )}

        {tab === 'copies' && (
          <div className="mt-6 space-y-4">
            {canEdit && (
              <Link
                to="/collection/add"
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground"
              >
                <Plus className="h-3 w-3" /> Add a copy
              </Link>
            )}
            {copiesQuery.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading copies…</p>
            ) : copies.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-12 text-center">
                <Package className="h-10 w-10 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">No live copies in the collection.</p>
              </div>
            ) : (
              <div className="grid max-w-4xl gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {copies.map((copy) => (
                  <CopyCard
                    key={copy.id}
                    item={copy}
                    movieId={movie.id}
                    canEdit={canEdit}
                    onEdit={setEditing}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {editing && (
        <CopyEditor movieId={movie.id} copy={editing} onClose={() => setEditing(null)} />
      )}
    </div>
  )
}
