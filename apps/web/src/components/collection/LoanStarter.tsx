import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { ArrowLeft, Loader2, X } from 'lucide-react'
import type { BarcodeCandidate } from '@mcu/shared'

import BarcodeScanner from '@/components/collection/BarcodeScanner'
import { LendButton } from '@/components/collection/LendButton'
import SearchBar from '@/components/SearchBar'
import { Button } from '@/components/ui/button'
import { StatePanel } from '@/components/ui/state-panel'
import { confirmBarcode, fetchCopies, formatLabel, lookupBarcode } from '@/lib/api'
import { listState, queryErrorMessage } from '@/lib/query-state'

interface Film {
  movieId: string
  title: string
}

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
                {copy.location ?? (copy.section ? `${copy.section}${copy.shelf ? ` · ${copy.shelf} shelf` : ''}` : 'No place recorded')}
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
 * your own films, or scan its barcode with the scanner Add a disc uses. **A scan resolves to a
 * film, never straight to a disc:** none of the 1,880 discs carried a barcode on 5 Oct, so the
 * lookup chain (remembered codes, the shelf, eBay, TMDB) names the film and the person picks
 * which of its discs. Choosing the film remembers the code through the existing confirm step,
 * so the next scan of it is instant; **nothing here writes a barcode onto a disc**, so a wrong
 * pick of copy cannot mislabel the catalogue.
 */
export function LoanStarter({ onClose }: { onClose: () => void }) {
  const [film, setFilm] = useState<Film | null>(null)
  const [notOnShelf, setNotOnShelf] = useState<string | null>(null)
  const [barcode, setBarcode] = useState<string | null>(null)

  const lookup = useMutation({ mutationFn: lookupBarcode })
  const choose = useMutation({
    mutationFn: async (candidate: BarcodeCandidate) => {
      if (barcode && candidate.source !== 'cache') {
        // Remembering the code is a convenience for the next scan; a failure to remember it
        // must not stand between the person and the loan.
        await confirmBarcode({
          barcode,
          title: candidate.title,
          source: candidate.source,
          movieId: candidate.movieId,
          tmdbId: candidate.tmdbId,
        }).catch(() => undefined)
      }
      return candidate
    },
    onSuccess: (candidate) => {
      if (candidate.movieId) setFilm({ movieId: candidate.movieId, title: candidate.title })
    },
  })

  function scanned(code: string) {
    setBarcode(code)
    setNotOnShelf(null)
    choose.reset()
    lookup.mutate(code)
  }

  // A film a barcode names is only useful here if it has a page in the catalogue.
  const known = (lookup.data?.candidates ?? []).filter((candidate) => candidate.movieId)

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

      {film ? (
        <FilmCopies film={film} onBack={() => setFilm(null)} />
      ) : (
        <>
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground">Search your films for it…</p>
            <SearchBar
              global={false}
              label="Search your films"
              placeholder="Search your films…"
              onPickOwned={(item) => {
                setNotOnShelf(null)
                setFilm({ movieId: item.id, title: item.title })
              }}
              onPickBeyond={(item) => setNotOnShelf(item.title)}
            />
            {notOnShelf ? (
              <p role="status" className="text-sm text-muted-foreground">
                {notOnShelf} is not on the shelf.
              </p>
            ) : null}
          </div>

          <div className="space-y-2 border-t border-border pt-4">
            <p className="text-sm text-muted-foreground">…or scan its barcode.</p>
            <BarcodeScanner onDetected={scanned} disabled={lookup.isPending || choose.isPending} />
            {lookup.isPending ? (
              <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                Looking up {barcode}…
              </p>
            ) : null}
            {lookup.isError ? (
              <p role="alert" className="text-sm text-destructive">
                {queryErrorMessage(lookup.error, 'That barcode could not be looked up.')}
              </p>
            ) : null}
            {lookup.isSuccess && known.length === 0 ? (
              <p role="status" className="text-sm text-muted-foreground">
                Nothing in the catalogue matches {lookup.data.barcode}. Search for the film instead.
              </p>
            ) : null}
            {known.length > 0 ? (
              <div className="space-y-2">
                <p className="text-sm text-foreground">Which film is it?</p>
                <ul className="flex flex-wrap gap-2">
                  {known.map((candidate) => (
                    <li key={`${candidate.movieId}-${candidate.source}`}>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={choose.isPending}
                        onClick={() => choose.mutate(candidate)}
                      >
                        {candidate.title}
                        {candidate.year ? ` (${String(candidate.year)})` : ''}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        </>
      )}
    </section>
  )
}
