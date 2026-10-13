import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import type { BarcodeCandidate } from '@mcu/shared'

import BarcodeScanner from '@/components/collection/BarcodeScanner'
import SearchBar from '@/components/SearchBar'
import { Button } from '@/components/ui/button'
import { confirmBarcode, lookupBarcode } from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

export interface FoundFilm {
  movieId: string
  title: string
}

/**
 * Find one of your own films by search or by scanning its barcode — Batch W3's finder,
 * shared since Y2 by Loans' "Lend or borrow" and "Move discs".
 *
 * **A scan resolves to a film, never straight to a disc:** none of the 1,880 discs carried a
 * barcode on 5 Oct, so the lookup chain (remembered codes, the shelf, eBay, TMDB) names the
 * film and the caller has the person pick which of its discs. Choosing the film remembers the
 * code through the existing confirm step, so the next scan of it is instant; **nothing here
 * writes a barcode onto a disc**, so a wrong pick of copy cannot mislabel the catalogue.
 */
export function FilmFinder({ onFound }: { onFound: (film: FoundFilm) => void }) {
  const [notOnShelf, setNotOnShelf] = useState<string | null>(null)
  const [barcode, setBarcode] = useState<string | null>(null)

  const lookup = useMutation({ mutationFn: lookupBarcode })
  const choose = useMutation({
    mutationFn: async (candidate: BarcodeCandidate) => {
      if (barcode && candidate.source !== 'cache') {
        // Remembering the code is a convenience for the next scan; a failure to remember it
        // must not stand between the person and the disc.
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
      if (candidate.movieId) onFound({ movieId: candidate.movieId, title: candidate.title })
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
    <>
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">Search your films for it…</p>
        <SearchBar
          global={false}
          label="Search your films"
          placeholder="Search your films…"
          onPickOwned={(item) => {
            setNotOnShelf(null)
            onFound({ movieId: item.id, title: item.title })
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
  )
}
