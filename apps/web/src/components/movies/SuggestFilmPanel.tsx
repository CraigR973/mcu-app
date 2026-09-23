import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check } from 'lucide-react'

import SearchBar from '@/components/SearchBar'
import { suggestMovieNightFilm, type BeyondResult, type MovieListItem } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

/** The film as the API takes it, plus the title to confirm it by. */
interface Suggestion {
  title: string
  input: Parameters<typeof suggestMovieNightFilm>[1]
}

/**
 * Put a film forward — Batch S7, `DECISIONS.md` #157's first two points.
 *
 * **Anyone in the session, and any film.** Batch 35 had no suggestion concept at all.
 *
 * **Batch T2 gave it the app's own search** in place of a type-then-press-Search form
 * with six text-only results. Results arrive as you type, with posters: your own films
 * first, with where they are and when you last saw them, then films that aren't on the
 * shelf, with where they stream. A film with a page here is suggested by its page (so
 * the card can show who has seen it); anything else by its TMDB id, with its title and
 * poster captured now because there is no row to read them from later.
 */
export function SuggestFilmPanel({ sessionId }: { sessionId: string }) {
  const queryClient = useQueryClient()
  const [added, setAdded] = useState<string | null>(null)

  const suggest = useMutation({
    mutationFn: ({ input }: Suggestion) => suggestMovieNightFilm(sessionId, input),
    onSuccess: (_list, suggestion) => {
      setAdded(suggestion.title)
      void queryClient.invalidateQueries({ queryKey: ['movie-night-candidates', sessionId] })
    },
    // A 409 here is "somebody already suggested it", which is agreement rather than a
    // failure — so it is said plainly instead of as an error.
    onError: () => setAdded(null),
  })

  const pickOwned = (item: MovieListItem) => suggest.mutate({ title: item.title, input: { movieId: item.id } })
  const pickBeyond = (item: BeyondResult) =>
    suggest.mutate({
      title: item.title,
      input: item.movieId
        ? { movieId: item.movieId }
        : { tmdbId: item.tmdbId, title: item.title, year: item.year, posterPath: item.posterPath },
    })

  return (
    <section className="w-full space-y-3 rounded-xl border border-border bg-card p-4" aria-labelledby="suggest-heading">
      <h2 id="suggest-heading" className="section-heading text-base">Suggest a film</h2>
      <p className="-mt-1 text-xs text-muted-foreground">
        Anything, not just what is on the shelf — anyone in the session can add to the list.
      </p>

      <SearchBar
        global={false}
        label="Search for a film to suggest"
        placeholder="Search any film…"
        onPickOwned={pickOwned}
        onPickBeyond={pickBeyond}
      />

      {added && !suggest.isPending ? (
        <p role="status" className="inline-flex items-center gap-1.5 text-sm text-success">
          <Check className="h-4 w-4" aria-hidden /> Added “{added}” to tonight's list.
        </p>
      ) : null}
      {suggest.isError ? (
        <p role="alert" className="text-sm text-destructive">{queryErrorMessage(suggest.error, 'That film could not be added.')}</p>
      ) : null}
    </section>
  )
}
