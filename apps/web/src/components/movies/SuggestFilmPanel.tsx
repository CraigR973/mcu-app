import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Search } from 'lucide-react'
import type { TmdbSearchResult } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { searchTmdb, suggestMovieNightFilm } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/**
 * Put a film forward — Batch S7, `DECISIONS.md` #157's first two points.
 *
 * **Anyone in the session, and any film.** Batch 35 had no suggestion concept at all:
 * `candidate_movies` was `select(Movie)` filtered by decade and rating, so a film outside
 * the Archive could never appear and nobody could name one.
 *
 * **It searches TMDB rather than the collection**, which is the whole point — the results
 * that are already on the shelf come back with a `movieId` and are suggested as such; the
 * rest are suggested by TMDB id, with their title and poster captured now because there
 * is no `movies` row to read them from later. "Shall we rent something" is a real answer
 * to "what shall we watch", and it was unsayable before this.
 */
export function SuggestFilmPanel({ sessionId }: { sessionId: string }) {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<TmdbSearchResult[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const search = useMutation({
    mutationFn: (q: string) => searchTmdb(q),
    onSuccess: (data) => {
      setResults(data.results)
      setError(null)
    },
    onError: (cause) => setError(queryErrorMessage(cause, 'That search could not be run.')),
  })

  const suggest = useMutation({
    mutationFn: (result: TmdbSearchResult) =>
      suggestMovieNightFilm(
        sessionId,
        result.movieId
          ? { movieId: result.movieId }
          : {
              tmdbId: result.tmdbId,
              title: result.title,
              year: result.year,
              posterPath: result.posterPath,
            },
      ),
    onSuccess: () => {
      setResults(null)
      setQuery('')
      setError(null)
      void queryClient.invalidateQueries({ queryKey: ['movie-night-candidates', sessionId] })
    },
    // A 409 here is "somebody already suggested it", which is agreement rather than a
    // failure — so it is said plainly instead of as an error.
    onError: (cause) => setError(queryErrorMessage(cause, 'That film could not be added.')),
  })

  return (
    <section className="w-full space-y-3 rounded-xl border border-border bg-card p-4" aria-labelledby="suggest-heading">
      <h2 id="suggest-heading" className="section-heading text-base">Suggest a film</h2>
      <p className="-mt-1 text-xs text-muted-foreground">
        Anything, not just what is on the shelf — anyone in the session can add to the list.
      </p>

      <form
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (query.trim().length >= 2) search.mutate(query.trim())
        }}
      >
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search any film…"
          aria-label="Search for a film to suggest"
        />
        <Button type="submit" variant="outline" disabled={search.isPending || query.trim().length < 2}>
          {search.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
          ) : (
            <Search className="h-4 w-4" aria-hidden />
          )}
          Search
        </Button>
      </form>

      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}

      {results !== null ? (
        results.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing found for “{query}”.</p>
        ) : (
          <ul className="divide-y divide-border">
            {results.slice(0, 6).map((result) => (
              <li key={result.tmdbId} className="flex items-center gap-3 py-2">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-foreground">
                    {result.title}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {result.year ?? 'Year unknown'}
                    {result.movieId ? ' · on the shelf' : ' · not in the collection'}
                  </span>
                </span>
                <Button
                  type="button"
                  size="sm"
                  disabled={suggest.isPending}
                  onClick={() => suggest.mutate(result)}
                >
                  <Plus className="h-4 w-4" aria-hidden />
                  Add
                </Button>
              </li>
            ))}
          </ul>
        )
      ) : null}
    </section>
  )
}
