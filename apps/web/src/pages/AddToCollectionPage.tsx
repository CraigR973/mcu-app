import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Check, Loader2, Plus, Search } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import CopyForm, { EMPTY_COPY } from '@/components/collection/CopyForm'
import DuplicatePrompt from '@/components/collection/DuplicatePrompt'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  checkDuplicate,
  DuplicateItemError,
  posterUrl,
  searchTmdb,
  type CollectionItemFields,
  type DuplicateCheck,
  type DuplicateReason,
  type TmdbSearchResult,
} from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { addOrQueue } from '@/lib/sync'

/** The film this disc is a copy of, however it was found. */
interface ChosenFilm {
  title: string
  year: number | null
  posterPath: string | null
  /** Set when the catalogue already has the film; otherwise the TMDB id creates it. */
  movieId: string | null
  tmdbId: number | null
}

function chosenFrom(result: TmdbSearchResult): ChosenFilm {
  return {
    title: result.title,
    year: result.year,
    posterPath: result.posterPath,
    // Attaching to the existing row rather than the TMDB id when we already have the
    // film: `movies.tmdb_id` is unique, and two rows would split one film's discs.
    movieId: result.movieId,
    tmdbId: result.movieId ? null : result.tmdbId,
  }
}

export default function AddToCollectionPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [film, setFilm] = useState<ChosenFilm | null>(null)
  const [fields, setFields] = useState<CollectionItemFields>(EMPTY_COPY)
  const [duplicate, setDuplicate] = useState<DuplicateCheck | null>(null)

  const searchQuery = useQuery({
    queryKey: ['tmdb-search', submitted],
    queryFn: () => searchTmdb(submitted),
    enabled: submitted.length >= 2,
  })

  function filmRef(chosen: ChosenFilm) {
    return chosen.movieId ? { movieId: chosen.movieId } : { tmdbId: chosen.tmdbId ?? 0 }
  }

  async function choose(result: TmdbSearchResult) {
    const chosen = chosenFrom(result)
    setFilm(chosen)
    setDuplicate(null)
    // §3.1 wants the warning *before* saving, so ask as soon as the film is known
    // rather than letting the save be rejected. The POST enforces it independently.
    try {
      const check = await checkDuplicate(filmRef(chosen), fields.formats)
      if (check.isDuplicate) setDuplicate(check)
    } catch {
      // A failed preflight must not block the add — the server-side 409 still holds.
    }
  }

  // The film's local id at the moment the mutation is defined, so `onSuccess` does not
  // have to narrow a nullable piece of state it cannot prove is still set.
  const chosenMovieId = film?.movieId ?? null

  const add = useMutation({
    mutationFn: (confirmDuplicate?: DuplicateReason) => {
      if (!film) throw new Error('Choose a film first')
      return addOrQueue({
        ...fields,
        ...(film.movieId ? { movieId: film.movieId } : { tmdbId: film.tmdbId ?? 0 }),
        confirmDuplicate,
      })
    },
    onSuccess: ({ item, queued }) => {
      void queryClient.invalidateQueries({ queryKey: ['movies'] })
      void queryClient.invalidateQueries({ queryKey: ['search'] })
      void queryClient.invalidateQueries({ queryKey: ['facets'] })
      if (item !== null) {
        void queryClient.invalidateQueries({ queryKey: ['movie-copies', item.movieId] })
        navigate(`/movies/${item.movieId}`)
        return
      }
      // Queued. A film added by TMDB id has no local row yet, so there is nothing to
      // navigate to — the banner is where this disc lives until it syncs. `film` is
      // captured here rather than read from state, which the mutation may outlive.
      const known = chosenMovieId
      if (queued && known !== null) {
        void queryClient.invalidateQueries({ queryKey: ['movie-copies', known] })
        navigate(`/movies/${known}`)
        return
      }
      navigate('/movies')
    },
    onError: (error) => {
      // The 409 is not a failure to report — it is §3.5's prompt arriving the other way
      // round, for a save that skipped or outran the preflight check.
      if (error instanceof DuplicateItemError) setDuplicate(error.duplicate)
    },
  })

  const results = searchQuery.data?.results ?? []
  const searchState = listState(searchQuery, results.length === 0)
  const canSave = film !== null && fields.formats.length > 0

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4 md:p-8">
      <div>
        <Link
          to="/movies"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back to movies
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-foreground">Add to the collection</h1>
        <p className="text-sm text-muted-foreground">
          Find the film, then say which disc it is and where it lives.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">1. Which film?</h2>
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            setSubmitted(query.trim())
          }}
        >
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search TMDB by title…"
            aria-label="Search for a film"
          />
          <Button type="submit" disabled={query.trim().length < 2}>
            {searchQuery.isFetching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            Search
          </Button>
        </form>

        {submitted.length >= 2 && searchState === 'error' && (
          <p className="text-xs text-destructive">
            {queryErrorMessage(searchQuery.error, 'Could not reach TMDB.')}
          </p>
        )}

        {submitted.length >= 2 && searchState === 'offline' && (
          <p className="text-xs text-muted-foreground">
            Waiting for the network — TMDB has not answered yet.
          </p>
        )}

        {/* Only once results genuinely arrived: a paused query has no results either,
            and "no films matched" would be a confident lie about a search that never ran. */}
        {submitted.length >= 2 && searchState === 'empty' && (
          <p className="text-xs text-muted-foreground">No films matched “{submitted}”.</p>
        )}

        <ul className="space-y-2">
          {results.map((result) => {
            const active =
              film !== null &&
              (film.movieId === result.movieId ||
                (film.tmdbId !== null && film.tmdbId === result.tmdbId))
            return (
              <li key={result.tmdbId}>
                <button
                  type="button"
                  onClick={() => void choose(result)}
                  className={`flex w-full items-start gap-3 rounded-lg border p-2 text-left transition-colors ${
                    active
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:bg-muted/50'
                  }`}
                >
                  <img
                    src={posterUrl(result.posterPath, 'w92')}
                    alt=""
                    className="h-16 w-11 shrink-0 rounded object-cover"
                    loading="lazy"
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{result.title}</span>
                      {result.year && (
                        <span className="text-xs text-muted-foreground">{result.year}</span>
                      )}
                      {result.inCollection && (
                        <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-secondary-foreground">
                          Already catalogued
                        </span>
                      )}
                    </span>
                    <span className="mt-0.5 line-clamp-2 block text-xs text-muted-foreground">
                      {result.overview}
                    </span>
                  </span>
                  {active && <Check className="h-4 w-4 shrink-0 text-primary" />}
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      {film && (
        <>
          {duplicate && (
            <DuplicatePrompt
              duplicate={duplicate}
              pending={add.isPending}
              onConfirm={(reason) => add.mutate(reason)}
              onCancel={() => {
                setDuplicate(null)
                setFilm(null)
              }}
            />
          )}

          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-foreground">
              2. Which disc, and where does it live?
            </h2>
            <CopyForm value={fields} onChange={setFields} disabled={add.isPending} />
          </section>

          {add.isError && !(add.error instanceof DuplicateItemError) && (
            <p className="text-sm text-destructive">
              {add.error instanceof Error ? add.error.message : 'Could not save that disc.'}
            </p>
          )}

          <div className="flex items-center gap-3">
            <Button
              type="button"
              disabled={!canSave || add.isPending}
              onClick={() => add.mutate(duplicate ? 'another_copy' : undefined)}
            >
              {add.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              Add “{film.title}”
            </Button>
            <Button type="button" variant="ghost" onClick={() => setFilm(null)}>
              Choose a different film
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
