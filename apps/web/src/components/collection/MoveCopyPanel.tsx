import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowRightLeft, Search } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { moveCopy, searchIdentify, type MoveCopy } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

interface Props {
  itemId: string
  movieId: string
  filmTitle: string
  onMoved: (moved: MoveCopy) => void
  /** Batch Y4: a doubt's "Move only this copy" opens straight on the search. */
  startOpen?: boolean
  /** Closing it, where the caller holds the button that opened it. */
  onCancel?: () => void
}

/**
 * "This copy is another film" — Batch X9 (CT46-01), on a copy card and, since Batch Y4
 * (#276), on a doubt about one copy. Either person since Y4, audited as whoever moved it.
 *
 * A film row could hold a right copy and a wrong one (the *French Connection II* row held
 * both discs of *The French Connection*), so a copy moves on its own, to the film TMDB says
 * it is, which the collection makes if it lacks it. The move is undone from Identify films'
 * recent list.
 */
export function MoveCopyPanel({ itemId, movieId, filmTitle, onMoved, startOpen = false, onCancel }: Props) {
  const [open, setOpen] = useState(startOpen)
  const [query, setQuery] = useState(filmTitle)
  const [searched, setSearched] = useState<string | null>(null)
  const search = useQuery({
    queryKey: ['identify-search', movieId, searched],
    queryFn: () => searchIdentify(movieId, searched ?? ''),
    enabled: open && searched !== null,
  })
  const move = useMutation({
    mutationFn: (target: number) => moveCopy(itemId, target),
    onSuccess: onMoved,
  })
  // The film the copy is on now is never offered.
  const found = (search.data?.candidates ?? []).filter((candidate) => candidate.inCollection?.movieId !== movieId)

  if (!open) {
    return (
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(true)}>
        <ArrowRightLeft aria-hidden /> This copy is another film
      </Button>
    )
  }

  return (
    <section className="space-y-2" aria-label="Move this copy to another film">
      <p className="text-sm text-muted-foreground">
        Which film is this copy? It moves on its own; the other copies and the watches stay here.
      </p>
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          if (query.trim()) setSearched(query.trim())
        }}
      >
        {/* Batch Y4: inside a doubt on a phone the box is narrow, so the buttons wrap below a
            title that can be read whole. */}
        <input
          className="form-control min-w-[12rem] flex-1"
          aria-label="Search TMDB for the film this copy is"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Button type="submit" size="sm" variant="secondary" disabled={move.isPending || !query.trim()}>
          <Search aria-hidden /> Search
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => {
            setOpen(false)
            onCancel?.()
          }}
        >
          Cancel
        </Button>
      </form>
      {search.isLoading ? <p className="text-xs text-muted-foreground">Searching TMDB…</p> : null}
      {search.isError ? (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(search.error, 'TMDB search is unavailable.')}
        </p>
      ) : null}
      {search.data && found.length === 0 ? (
        <p className="text-xs text-muted-foreground">No other films found for “{search.data.query}”.</p>
      ) : null}
      {found.length > 0 ? (
        <ul className="divide-y divide-border" aria-label="Films this copy may be">
          {found.map((candidate) => (
            <li key={candidate.tmdbId} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span className="text-sm text-foreground">
                {candidate.title}
                {candidate.year ? <span className="text-muted-foreground"> ({candidate.year})</span> : null}
                {candidate.inCollection ? (
                  <span className="block text-xs text-muted-foreground">Already in the collection</span>
                ) : null}
              </span>
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled={move.isPending}
                onClick={() => move.mutate(candidate.tmdbId)}
              >
                Move this copy here
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {move.isError ? (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(move.error, 'The copy could not be moved.')}
        </p>
      ) : null}
    </section>
  )
}
