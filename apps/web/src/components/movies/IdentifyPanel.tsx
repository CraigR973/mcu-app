import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Check, Search, Sparkles } from 'lucide-react'

import {
  fetchCandidates,
  identifyMovie,
  posterUrl,
  type Candidate,
  type MovieDetail,
} from '@/lib/api'

interface Props {
  movieId: string
  storedTitle: string
  onIdentified: (movie: MovieDetail) => void
}

function CandidateCard({
  candidate,
  choosing,
  onChoose,
}: {
  candidate: Candidate
  choosing: boolean
  onChoose: () => void
}) {
  return (
    <article className="flex gap-3 rounded-xl border border-border bg-card p-3 shadow-sm">
      <img
        src={posterUrl(candidate.posterPath, 'w185')}
        alt=""
        className="h-32 w-[5.35rem] shrink-0 rounded-md bg-muted object-cover"
        loading="lazy"
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <div>
          <h3 className="font-semibold leading-tight text-foreground">{candidate.title}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {candidate.year ?? 'Year unknown'} · {Math.round(candidate.confidence * 100)}% match
          </p>
        </div>
        <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-muted-foreground">
          {candidate.overview || 'TMDB has no overview for this film.'}
        </p>
        <button
          type="button"
          onClick={onChoose}
          disabled={choosing}
          className="mt-auto inline-flex w-fit items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-opacity disabled:opacity-60"
        >
          <Check className="h-3.5 w-3.5" />
          {choosing ? 'Saving…' : 'This is it'}
        </button>
      </div>
    </article>
  )
}

export default function IdentifyPanel({ movieId, storedTitle, onIdentified }: Props) {
  const [input, setInput] = useState(storedTitle)
  const [submittedQuery, setSubmittedQuery] = useState<string | undefined>()
  const candidates = useQuery({
    queryKey: ['movie-candidates', movieId, submittedQuery ?? storedTitle],
    queryFn: () => fetchCandidates(movieId, submittedQuery),
    staleTime: 5 * 60 * 1000,
  })
  const identify = useMutation({
    mutationFn: (tmdbId: number) => identifyMovie(movieId, tmdbId),
    onSuccess: onIdentified,
  })

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const query = input.trim()
    if (query) setSubmittedQuery(query)
  }

  return (
    <section className="rounded-2xl border border-amber-400/40 bg-amber-400/10 p-4 md:p-5">
      <div className="flex items-start gap-3">
        <span className="rounded-full bg-amber-400 p-2 text-zinc-950">
          <Sparkles className="h-4 w-4" />
        </span>
        <div>
          <h2 className="font-semibold text-foreground">Which film is this?</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Choose a match to add its poster, overview and cast. If none look right, search
            TMDB with another title.
          </p>
        </div>
      </div>

      <form onSubmit={submit} className="mt-4 flex gap-2">
        <label className="sr-only" htmlFor="candidate-query">Search TMDB for another title</label>
        <input
          id="candidate-query"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          className="h-10 min-w-0 flex-1 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
        />
        <button
          type="submit"
          className="inline-flex h-10 items-center gap-1.5 rounded-md bg-secondary px-3 text-sm font-medium text-secondary-foreground"
        >
          <Search className="h-4 w-4" /> Search
        </button>
      </form>

      {candidates.isLoading && (
        <p className="py-8 text-center text-sm text-muted-foreground">Finding likely matches…</p>
      )}
      {candidates.isError && (
        <p className="py-6 text-sm text-destructive">
          {candidates.error instanceof Error
            ? candidates.error.message
            : 'Could not search TMDB. Please try again.'}
        </p>
      )}
      {candidates.data?.candidates.length === 0 && (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No matches found. Try a shorter title or add the release year.
        </p>
      )}
      {candidates.data && candidates.data.candidates.length > 0 && (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {candidates.data.candidates.map((candidate) => (
            <CandidateCard
              key={candidate.tmdbId}
              candidate={candidate}
              choosing={identify.isPending && identify.variables === candidate.tmdbId}
              onChoose={() => identify.mutate(candidate.tmdbId)}
            />
          ))}
        </div>
      )}
      {identify.isError && (
        <p className="mt-3 text-sm text-destructive">
          {identify.error instanceof Error ? identify.error.message : 'Could not save that match.'}
        </p>
      )}
    </section>
  )
}
