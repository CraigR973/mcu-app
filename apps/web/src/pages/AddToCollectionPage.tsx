import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Loader2, Plus, Search } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import CopyForm, { EMPTY_COPY } from '@/components/collection/CopyForm'
import DuplicatePrompt from '@/components/collection/DuplicatePrompt'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/ui/page-header'
import { Badge } from '@/components/ui/badge'
import { Poster } from '@/components/movies/Poster'
import {
  checkDuplicate,
  DuplicateItemError,
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
    <div className="page-shell-narrow space-y-7">
      <PageHeader backTo="/movies" backLabel="Back to the archive" eyebrow="Catalogue entry" title="Add a disc" description="Find the film first, then record the exact edition, format and shelf location." />

      <section className="archive-panel space-y-4 p-4 sm:p-6" aria-labelledby="choose-film-heading">
        <div><p className="page-kicker">Step 1</p><h2 id="choose-film-heading" className="section-heading">Which film?</h2></div>
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
          <p role="alert" className="text-sm text-destructive">
            {queryErrorMessage(searchQuery.error, 'Could not reach TMDB.')}
          </p>
        )}

        {submitted.length >= 2 && searchState === 'offline' && (
          <p className="text-sm text-muted-foreground">
            Waiting for the network — TMDB has not answered yet.
          </p>
        )}

        {/* Only once results genuinely arrived: a paused query has no results either,
            and "no films matched" would be a confident lie about a search that never ran. */}
        {submitted.length >= 2 && searchState === 'empty' && (
          <p className="text-sm text-muted-foreground">No films matched “{submitted}”.</p>
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
                  aria-pressed={active}
                  className={`flex min-h-20 w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors ${
                    active
                      ? 'border-primary bg-primary/5'
                      : 'border-border hover:bg-muted/50'
                  }`}
                >
                  <Poster path={result.posterPath} title={result.title} size="w92" decorative className="h-16 w-11 shrink-0 rounded-sm" />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{result.title}</span>
                      {result.year && (
                        <span className="text-xs text-muted-foreground">{result.year}</span>
                      )}
                      {result.inCollection && (
                        <Badge tone="success">Already catalogued</Badge>
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

          <section className="archive-panel space-y-4 p-4 sm:p-6" aria-labelledby="describe-disc-heading">
            <div><p className="page-kicker">Step 2</p><h2 id="describe-disc-heading" className="section-heading">Which edition, and where does it live?</h2></div>
            <CopyForm value={fields} onChange={setFields} disabled={add.isPending} />
          </section>

          {add.isError && !(add.error instanceof DuplicateItemError) && (
            <p role="alert" className="text-sm text-destructive">
              {add.error instanceof Error ? add.error.message : 'Could not save that disc.'}
            </p>
          )}

          <div className="sticky bottom-0 -mx-4 flex flex-col gap-2 border-t border-border bg-background/95 px-4 py-4 backdrop-blur sm:static sm:mx-0 sm:flex-row sm:items-center sm:border-0 sm:bg-transparent sm:p-0">
            <Button
              type="button"
              className="w-full min-w-0 sm:w-auto"
              disabled={!canSave || add.isPending}
              onClick={() => add.mutate(duplicate ? 'another_copy' : undefined)}
            >
              {add.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              <span className="truncate">Add “{film.title}”</span>
            </Button>
            <Button type="button" className="w-full sm:w-auto" variant="ghost" onClick={() => setFilm(null)}>
              Choose a different film
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
