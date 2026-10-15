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
import { queryErrorMessage } from '@/lib/query-state'

interface Props {
  movieId: string
  storedTitle: string
  onIdentified: (movie: MovieDetail) => void
  /** Batch Y3: the title is a series, set aside as one or identified as one, so TMDB's
   *  series are offered before its films. */
  preferSeries?: boolean
}

type Choice = Pick<Candidate, 'tmdbId' | 'mediaType'>

function CandidateCard({
  candidate,
  choosing,
  onChoose,
}: {
  candidate: Candidate
  choosing: boolean
  onChoose: () => void
}) {
  const series = candidate.mediaType === 'tv'
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
            {series ? 'TV series · ' : ''}
            {candidate.year ?? 'Year unknown'} · {Math.round(candidate.confidence * 100)}% match
          </p>
        </div>
        <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-muted-foreground">
          {candidate.overview || `TMDB has no overview for this ${series ? 'series' : 'film'}.`}
        </p>
        <button
          type="button"
          onClick={onChoose}
          disabled={choosing}
          aria-label={`This is it: ${candidate.title}${series ? ', the TV series' : ''}`}
          className="mt-auto inline-flex w-fit items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-opacity disabled:opacity-60"
        >
          <Check className="h-3.5 w-3.5" />
          {choosing ? 'Saving…' : 'This is it'}
        </button>
      </div>
    </article>
  )
}

export default function IdentifyPanel({ movieId, storedTitle, onIdentified, preferSeries = false }: Props) {
  const [input, setInput] = useState(storedTitle)
  const [submittedQuery, setSubmittedQuery] = useState<string | undefined>()
  const candidates = useQuery({
    queryKey: ['movie-candidates', movieId, submittedQuery ?? storedTitle],
    queryFn: () => fetchCandidates(movieId, submittedQuery),
    staleTime: 5 * 60 * 1000,
  })
  const identify = useMutation({
    mutationFn: ({ tmdbId, mediaType }: Choice) => identifyMovie(movieId, tmdbId, mediaType),
    onSuccess: onIdentified,
  })

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const query = input.trim()
    if (query) setSubmittedQuery(query)
  }

  const films = candidates.data?.candidates ?? []
  const series = candidates.data?.seriesCandidates ?? []
  // Batch Y3: TMDB numbers films and series separately, so a card is known by both.
  const groups = [
    { key: 'film', label: 'Films', items: films },
    { key: 'tv', label: 'TV series', items: series },
  ]
  if (preferSeries) groups.reverse()

  return (
    <section className="rounded-2xl border border-warning/40 bg-warning/10 p-4 md:p-5">
      <div className="flex items-start gap-3">
        <span className="rounded-full bg-warning p-2 text-warning-foreground">
          <Sparkles className="h-4 w-4" />
        </span>
        <div>
          <h2 className="font-semibold text-foreground">{preferSeries ? 'Which series is this?' : 'Which film is this?'}</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Choose a match to add its poster, overview and cast. TMDB&apos;s films and TV series
            are both listed. If none look right, search TMDB with another title.
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
          {queryErrorMessage(candidates.error, 'Could not search TMDB. Please try again.')}
        </p>
      )}
      {candidates.data && films.length === 0 && series.length === 0 && (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No matches found. Try a shorter title or add the release year.
        </p>
      )}
      {groups.map((group) =>
        group.items.length > 0 ? (
          <section key={group.key} className="mt-4" aria-label={group.label}>
            <h3 className="field-label mb-2">{group.label}</h3>
            <div className="grid gap-3 lg:grid-cols-2">
              {group.items.map((candidate) => (
                <CandidateCard
                  key={`${candidate.mediaType}-${candidate.tmdbId}`}
                  candidate={candidate}
                  choosing={
                    identify.isPending &&
                    identify.variables?.tmdbId === candidate.tmdbId &&
                    identify.variables?.mediaType === candidate.mediaType
                  }
                  onChoose={() => identify.mutate({ tmdbId: candidate.tmdbId, mediaType: candidate.mediaType })}
                />
              ))}
            </div>
          </section>
        ) : null,
      )}
      {identify.isError && (
        <p className="mt-3 text-sm text-destructive">
          {queryErrorMessage(identify.error, 'Could not save that match.')}
        </p>
      )}
    </section>
  )
}
