import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, X } from 'lucide-react'

import { FilmFinder, type FoundFilm as Film } from '@/components/collection/FilmFinder'
import { LendButton } from '@/components/collection/LendButton'
import { StatePanel } from '@/components/ui/state-panel'
import { fetchCopies, formatLabel } from '@/lib/api'
import { placeLabel } from '@/lib/place'
import { listState, queryErrorMessage } from '@/lib/query-state'

/** One film's discs on the shelf, each with Lend, Borrow, or Returned when it is out. */
function FilmCopies({ film, onBack }: { film: Film; onBack: () => void }) {
  const copiesQuery = useQuery({
    queryKey: ['movie-copies', film.movieId, 'owned'],
    queryFn: () => fetchCopies(film.movieId),
  })
  const copies = copiesQuery.data ?? []
  const state = listState(copiesQuery, copies.length === 0)

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={onBack}
        className="flex min-h-11 items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Another disc
      </button>
      <h3 className="font-display text-lg font-semibold text-foreground">{film.title}</h3>
      {state === 'loading' ? <StatePanel compact tone="loading" title="Finding its discs" /> : null}
      {state === 'offline' ? <StatePanel compact tone="offline" title="Its discs need a connection" /> : null}
      {state === 'error' ? (
        <StatePanel
          compact
          tone="error"
          title="Its discs could not be read"
          description={queryErrorMessage(copiesQuery.error, 'Could not load the discs.')}
        />
      ) : null}
      {state === 'empty' ? (
        <p className="text-sm text-muted-foreground">No disc of this film is on the shelf.</p>
      ) : null}
      {state === 'ready' ? (
        <ul className="space-y-3">
          {copies.map((copy) => (
            <li key={copy.id} className="rounded-lg border border-border bg-card p-3">
              <p className="font-semibold text-foreground">
                {copy.formats.map((format) => formatLabel(format) ?? format).join(' + ') || 'Format not recorded'}
                {copy.edition ? <span className="font-normal text-muted-foreground"> · {copy.edition}</span> : null}
              </p>
              <p className="mb-3 text-xs text-muted-foreground">
                {placeLabel(copy)}
              </p>
              <LendButton collectionItemId={copy.id} />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

/**
 * Loans' "Lend or borrow" — Batch W3 (`DECISIONS.md` #249).
 *
 * Find the disc, then lend it, borrow it, or say it is back. **Two ways to find it:** search
 * your own films, or scan its barcode with the scanner Add a disc uses — `FilmFinder`, shared
 * with Move discs since Y2. A scan names the film and the person picks which of its discs.
 */
export function LoanStarter({ onClose }: { onClose: () => void }) {
  const [film, setFilm] = useState<Film | null>(null)

  return (
    <section aria-labelledby="loan-starter-heading" className="archive-panel space-y-4 p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <h2 id="loan-starter-heading" className="section-heading text-lg">
          Lend or borrow a disc
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="touch-target -mr-2 -mt-2 flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {film ? <FilmCopies film={film} onBack={() => setFilm(null)} /> : <FilmFinder onFound={setFilm} />}
    </section>
  )
}
