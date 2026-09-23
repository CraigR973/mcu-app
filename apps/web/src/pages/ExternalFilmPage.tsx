import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Bookmark, Check, ExternalLink, HelpCircle, Loader2, Popcorn } from 'lucide-react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { Poster } from '@/components/movies/Poster'
import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import {
  addWanted,
  fetchExternalFilm,
  fetchMovieNights,
  OFFER_KIND_LABELS,
  providerLogoUrl,
  suggestMovieNightFilm,
  type ExternalFilm,
  type OfferKind,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

const OFFER_ORDER: OfferKind[] = ['flatrate', 'rent', 'buy']

function runtimeLabel(minutes: number | null): string | null {
  if (!minutes) return null
  return `${String(Math.floor(minutes / 60))}h ${String(minutes % 60)}m`
}

function WhereToWatch({ film }: { film: ExternalFilm }) {
  if (film.offers.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        TMDB doesn't list it to stream, rent or buy in {film.region === 'GB' ? 'the UK' : film.region} right now.
      </p>
    )
  }
  return (
    <div className="space-y-3">
      {OFFER_ORDER.map((kind) => {
        const offers = film.offers.filter((offer) => offer.kind === kind)
        if (offers.length === 0) return null
        return (
          <div key={kind}>
            <p className="field-label">{OFFER_KIND_LABELS[kind]}</p>
            <ul className="mt-1 flex flex-wrap gap-2">
              {offers.map((offer) => (
                <li key={`${kind}-${String(offer.providerId)}`} className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1 text-sm">
                  {offer.logoPath ? (
                    <img src={providerLogoUrl(offer.logoPath)} alt="" className="h-6 w-6 rounded" loading="lazy" />
                  ) : null}
                  {offer.providerName}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
      {film.link ? (
        // TMDB's terms ask for this link beside their availability data, and it is the only
        // honest place for prices: the API gives none.
        <a href={film.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline">
          Prices and links on TMDB <ExternalLink className="h-3.5 w-3.5" aria-hidden />
        </a>
      ) : null}
    </div>
  )
}

/**
 * The card for a film the collection does not hold — Batch T2, snag 14.
 *
 * Reached from search. An **owned** film is sent to its own page instead: a stranger's
 * card for something on the shelf would be the duplicate the batch exists to prevent.
 */
export default function ExternalFilmPage() {
  const { tmdbId = '' } = useParams()
  const id = Number(tmdbId)
  const valid = Number.isInteger(id) && id > 0
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const maybeOwned = (location.state as { maybeOwned?: { movieId: string; title: string } | null } | null)?.maybeOwned ?? null
  const [nightId, setNightId] = useState('')

  const filmQuery = useQuery({
    queryKey: ['external-film', id],
    queryFn: () => fetchExternalFilm(id),
    enabled: valid,
  })
  const film = filmQuery.data
  const nights = useQuery({ queryKey: ['movie-nights'], queryFn: fetchMovieNights })
  const openNights = (nights.data?.items ?? []).filter((night) => night.status === 'open')

  useEffect(() => {
    if (film?.owned && film.movieId) navigate(`/movies/${film.movieId}`, { replace: true })
  }, [film, navigate])

  const want = useMutation({
    mutationFn: () => addWanted({ tmdbId: id }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['external-film', id] })
      void queryClient.invalidateQueries({ queryKey: ['wanted'] })
    },
  })

  const suggest = useMutation({
    mutationFn: (sessionId: string) => {
      if (!film) throw new Error('The film has not loaded yet.')
      return suggestMovieNightFilm(
        sessionId,
        film.movieId
          ? { movieId: film.movieId }
          : { tmdbId: film.tmdbId, title: film.title, year: film.year, posterPath: film.posterPath },
      )
    },
    onSuccess: (_list, sessionId) => navigate(`/movie-night/${sessionId}`),
  })

  const state = valid ? listState(filmQuery, false) : 'error'
  const chosenNight = nightId || openNights[0]?.id || ''

  return (
    <div className="page-shell-narrow space-y-6">
      {/* A desktop back link: on a phone the top bar has the arrow (Batch T3). */}
      <button type="button" onClick={() => navigate(-1)} className="hidden min-h-11 items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground lg:inline-flex">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Back
      </button>

      {state === 'loading' ? <StatePanel tone="loading" title="Looking the film up" /> : null}
      {state === 'offline' ? <StatePanel tone="offline" title="This film needs a connection" description="Films outside the collection come from TMDB, so they can't be shown offline." /> : null}
      {state === 'error' ? (
        <StatePanel tone="error" title="This film couldn't be shown" description={valid ? queryErrorMessage(filmQuery.error, 'TMDB did not answer.') : 'That is not a TMDB film id.'} />
      ) : null}

      {film && !film.owned ? (
        <article className="space-y-6">
          <header className="flex gap-4">
            <Poster path={film.posterPath} title={film.title} size="w185" className="h-40 w-[6.75rem] shrink-0 rounded-md" />
            <div className="min-w-0">
              <p className="page-kicker">Not in the collection</p>
              <h1 className="font-display text-2xl font-semibold leading-tight text-foreground">{film.title}</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {[film.year ? String(film.year) : null, runtimeLabel(film.runtimeMinutes), film.genres.slice(0, 3).join(' · ') || null].filter(Boolean).join(' · ')}
              </p>
              {film.directors.length > 0 ? (
                <p className="mt-1 text-sm text-muted-foreground">Directed by {film.directors.join(' and ')}</p>
              ) : null}
            </div>
          </header>

          {maybeOwned ? (
            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-warning/45 bg-warning/10 p-3 text-sm">
              <HelpCircle className="h-4 w-4 shrink-0 text-warning" aria-hidden />
              <span className="min-w-0 flex-1">
                This might be your copy of “{maybeOwned.title}”, which hasn't been identified yet.
              </span>
              <Button asChild size="sm" variant="outline">
                <Link to={`/movies/${maybeOwned.movieId}`}>Open it</Link>
              </Button>
            </div>
          ) : null}

          {film.overview ? <p className="text-sm leading-6 text-foreground">{film.overview}</p> : null}
          {film.cast.length > 0 ? (
            <p className="text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">Starring</span> {film.cast.join(', ')}
            </p>
          ) : null}

          <section className="archive-panel space-y-3 p-4" aria-labelledby="where-to-watch">
            <h2 id="where-to-watch" className="section-heading">Where to watch</h2>
            <WhereToWatch film={film} />
          </section>

          <section className="flex flex-wrap items-center gap-3" aria-label="What to do with it">
            {film.wanted ? (
              <span className="inline-flex items-center gap-2 text-sm font-semibold text-success">
                <Check className="h-4 w-4" aria-hidden /> On your Wanted list
              </span>
            ) : (
              <Button type="button" onClick={() => want.mutate()} disabled={want.isPending}>
                {want.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Bookmark className="h-4 w-4" aria-hidden />}
                Add to Wanted
              </Button>
            )}

            {openNights.length > 0 ? (
              <span className="inline-flex flex-wrap items-center gap-2">
                {openNights.length > 1 ? (
                  <select className="select-control" value={chosenNight} onChange={(event) => setNightId(event.target.value)} aria-label="Which movie night">
                    {openNights.map((night) => (
                      <option key={night.id} value={night.id}>
                        Movie night of {new Date(night.createdAt).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                      </option>
                    ))}
                  </select>
                ) : null}
                <Button type="button" variant="outline" onClick={() => suggest.mutate(chosenNight)} disabled={suggest.isPending || !chosenNight}>
                  <Popcorn className="h-4 w-4" aria-hidden /> Suggest for movie night
                </Button>
              </span>
            ) : null}
          </section>

          {want.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(want.error, 'It could not be added to Wanted.')}</p> : null}
          {suggest.isError ? <p role="alert" className="text-sm text-destructive">{queryErrorMessage(suggest.error, 'It could not be suggested.')}</p> : null}
        </article>
      ) : null}
    </div>
  )
}
