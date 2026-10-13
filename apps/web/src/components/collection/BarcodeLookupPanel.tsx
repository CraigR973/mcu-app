import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Check, Loader2, RotateCcw, Search } from 'lucide-react'

import BarcodeScanner from './BarcodeScanner'
import { Poster } from '@/components/movies/Poster'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  confirmBarcode,
  lookupBarcode,
  type BarcodeCandidate,
  type BarcodeLookup,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

interface Props {
  onConfirmed: (candidate: BarcodeCandidate, barcode: string) => Promise<void>
  onManualSearch: (barcode: string) => void
  onBarcodeChange: (barcode: string | null) => void
}

function sourceLabel(source: BarcodeCandidate['source']): string {
  if (source === 'cache') return 'Confirmed before'
  if (source === 'collection') return 'In your collection'
  if (source === 'ebay') return 'eBay + TMDB'
  if (source === 'tmdb') return 'TMDB'
  return 'Manual match'
}

/**
 * Phase 3.4's deliberately two-step flow: look up, then confirm.
 *
 * A candidate cannot cross this component boundary until the person presses the
 * confirmation button. That structural split is the guard against a plausible
 * wrong-edition match being silently added to the catalogue.
 */
export default function BarcodeLookupPanel({
  onConfirmed,
  onManualSearch,
  onBarcodeChange,
}: Props) {
  const [barcode, setBarcode] = useState<string | null>(null)
  const [resolution, setResolution] = useState<BarcodeLookup | null>(null)

  const lookup = useMutation({
    mutationFn: lookupBarcode,
    onSuccess: setResolution,
  })

  const confirm = useMutation({
    mutationFn: async (candidate: BarcodeCandidate) => {
      if (!barcode) throw new Error('Scan a barcode first')
      if (!candidate.movieId && !candidate.tmdbId) {
        throw new Error('Search by title so the film can be identified before adding it.')
      }
      if (candidate.source !== 'cache') {
        await confirmBarcode({
          barcode,
          title: candidate.title,
          source: candidate.source,
          movieId: candidate.movieId,
          tmdbId: candidate.tmdbId,
        })
      }
      await onConfirmed(candidate, barcode)
    },
  })

  function detected(code: string) {
    setBarcode(code)
    onBarcodeChange(code)
    setResolution(null)
    confirm.reset()
    lookup.mutate(code)
  }

  function reset() {
    setBarcode(null)
    onBarcodeChange(null)
    setResolution(null)
    lookup.reset()
    confirm.reset()
  }

  const candidates = resolution?.candidates ?? []

  return (
    <div className="space-y-4">
      {!barcode && <BarcodeScanner onDetected={detected} disabled={lookup.isPending} />}

      {barcode && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-muted/30 p-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted-foreground">
              Scanned code
            </p>
            <p className="font-mono text-base font-semibold tracking-wide text-foreground">
              {barcode}
            </p>
          </div>
          <Button type="button" variant="ghost" onClick={reset} disabled={lookup.isPending || confirm.isPending}>
            <RotateCcw className="h-4 w-4" />
            Scan another
          </Button>
        </div>
      )}

      {lookup.isPending && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <Loader2 className="h-4 w-4 animate-spin" />
          Looking up this barcode…
        </p>
      )}

      {lookup.isError && (
        <div className="space-y-3" role="alert">
          <p className="text-sm text-destructive">
            {queryErrorMessage(lookup.error, 'That barcode could not be looked up.')}
          </p>
          <p className="text-sm text-muted-foreground">
            Check the digits printed below the bars, then scan or enter them again.
          </p>
        </div>
      )}

      {resolution?.alreadyOwned && (
        <div className="rounded-lg border border-success/40 bg-success/10 p-3 text-sm text-foreground">
          <p className="font-medium">This exact barcode is already in the collection.</p>
          <p className="mt-1 text-muted-foreground">
            You can still confirm it if this is another copy or a format upgrade.
          </p>
        </div>
      )}

      {resolution && candidates.length > 0 && (
        <div className="space-y-3" aria-labelledby="barcode-candidates-heading">
          <div>
            <p className="page-kicker">Confirmation required</p>
            <h3 id="barcode-candidates-heading" className="text-base font-semibold text-foreground">
              Is this the film on the case?
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Barcode searches can confuse editions and bundles. Check the title and year before continuing.
            </p>
          </div>
          <ul className="space-y-2">
            {candidates.map((candidate, index) => {
              const confirmable = Boolean(candidate.movieId || candidate.tmdbId)
              const key = `${candidate.source}-${candidate.tmdbId ?? candidate.movieId ?? candidate.title}-${index}`
              return (
                <li key={key} className="rounded-lg border border-border p-3">
                  <div className="flex items-start gap-3">
                    <Poster
                      path={candidate.posterPath}
                      title={candidate.title}
                      size="w92"
                      decorative
                      className="h-20 w-14 shrink-0 rounded-sm"
                    />
                    <div className="min-w-0 flex-1 space-y-2">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium text-foreground">{candidate.title}</p>
                          {candidate.year && (
                            <span className="text-xs text-muted-foreground">{candidate.year}</span>
                          )}
                          <Badge tone={candidate.source === 'collection' ? 'success' : 'neutral'}>
                            {sourceLabel(candidate.source)}
                          </Badge>
                        </div>
                        {candidate.evidence && (
                          <p className="mt-1 text-xs text-muted-foreground">{candidate.evidence}</p>
                        )}
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => confirm.mutate(candidate)}
                        disabled={!confirmable || confirm.isPending}
                      >
                        {confirm.isPending && confirm.variables === candidate ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Check className="h-4 w-4" />
                        )}
                        This is the disc
                      </Button>
                      {!confirmable && (
                        <p className="text-xs text-muted-foreground">
                          This old cached answer needs a title search before it can be added.
                        </p>
                      )}
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
          <Button type="button" variant="outline" onClick={() => onManualSearch(resolution.barcode)}>
            <Search className="h-4 w-4" />
            None of these — search by title
          </Button>
        </div>
      )}

      {resolution && candidates.length === 0 && (
        <div className="space-y-3 rounded-lg border border-border bg-muted/20 p-4">
          <div>
            <p className="font-medium text-foreground">No film matched this barcode.</p>
            <p className="mt-1 text-sm text-muted-foreground">
              The code is valid, but it is not in the cache and the catalogue search found no reliable title.
            </p>
          </div>
          <Button type="button" onClick={() => onManualSearch(resolution.barcode)}>
            <Search className="h-4 w-4" />
            Search by title
          </Button>
        </div>
      )}

      {confirm.isError && (
        <p role="alert" className="text-sm text-destructive">
          {queryErrorMessage(confirm.error, 'That match could not be confirmed.')}
        </p>
      )}
    </div>
  )
}
