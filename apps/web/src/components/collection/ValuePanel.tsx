import { useMutation } from '@tanstack/react-query'
import { ExternalLink, Loader2, PoundSterling, Tag } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  fetchEbayListingUrl,
  fetchEbayPriceEstimate,
  formatLabel,
  type EbayPriceEstimate,
  type EbayPriceSegment,
} from '@/lib/api'
import { queryErrorMessage } from '@/lib/query-state'

import { valueBehind } from './value-words'

/**
 * What a disc is currently being asked for on eBay, and a link to list it — §4.1, §4.3.
 *
 * **Three things about this panel are requirements rather than choices.**
 *
 * 1. **It says "current asking prices", every time.** Sold comps are unobtainable —
 *    Marketplace Insights is closed to new applicants and eBay put sold listings behind a
 *    login wall in late August 2026 (`DECISIONS.md` #16, re-confirmed by #126) — so a
 *    surface that implied "this is what it sells for" would be stating something nobody
 *    can know. The server sends the exact words in `basis`; they are rendered, not
 *    re-typed here.
 *
 * 2. **Every price shows its sample size.** `DECISIONS.md` #129 measured a naive
 *    keyword-search median at £30.45 against a real £12.21. Both look equally reasonable
 *    on a card; only "from 56 listings" versus "from 3" tells them apart.
 *
 * 3. **Nothing is fetched until asked.** Each estimate spends a unit of a finite
 *    5,000-a-day production quota, and this panel sits inside every copy on a film's page.
 *    Loading on mount would spend one per copy per visit, for a number nobody asked for.
 */
export function ValuePanel({
  filmTitle,
  year,
  formatCode,
  condition,
  isSeries = false,
}: {
  filmTitle: string
  year?: number | null
  formatCode?: string | null
  condition?: string | null
  /** Batch X6: a TV title, whose own "Complete Series" box sets are not another product. */
  isSeries?: boolean
}) {
  const [estimate, setEstimate] = useState<EbayPriceEstimate | null>(null)

  const priceCheck = useMutation({
    mutationFn: () => fetchEbayPriceEstimate({ filmTitle, formatCode, isSeries }),
    onSuccess: setEstimate,
  })

  const listing = useMutation({
    mutationFn: () => fetchEbayListingUrl({ filmTitle, year, formatCode, condition, isSeries }),
    onSuccess: (result) => {
      // `noopener` is not optional on a `_blank` link: without it the opened page holds a
      // reference to this one through `window.opener`.
      window.open(result.url, '_blank', 'noopener,noreferrer')
    },
  })

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => priceCheck.mutate()}
          disabled={priceCheck.isPending}
        >
          {priceCheck.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <PoundSterling aria-hidden />
          )}
          What is it worth?
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={() => listing.mutate()}
          disabled={listing.isPending}
        >
          {listing.isPending ? (
            <Loader2 className="animate-spin" aria-hidden />
          ) : (
            <Tag aria-hidden />
          )}
          List on eBay
          <ExternalLink aria-hidden />
        </Button>
      </div>

      {priceCheck.isError && (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(priceCheck.error, 'eBay could not be reached.')}
        </p>
      )}
      {listing.isError && (
        <p role="alert" className="text-sm text-destructive-text">
          {queryErrorMessage(listing.error, 'The listing link could not be built.')}
        </p>
      )}

      {estimate ? <Estimate estimate={estimate} /> : null}
    </div>
  )
}

function money(segment: EbayPriceSegment): string {
  return segment.currency === 'GBP' ? `£${segment.median}` : `${segment.median} ${segment.currency}`
}

/**
 * The estimate itself. Exported so its markup can be tested directly — the three
 * requirements in {@link ValuePanel}'s note are properties of *this* view, and a test that
 * could only reach it by driving a network mutation would be testing react-query.
 */
export function Estimate({ estimate }: { estimate: EbayPriceEstimate }) {
  // A search that matched nothing is an answer — a rare disc, or a title eBay spells
  // differently — not an error, and it is reported as one rather than as a blank.
  if (!estimate.headline) {
    return (
      <div className="rounded-md border border-border bg-muted/40 px-3 py-2.5 text-sm">
        <p className="text-muted-foreground">
          Nothing on eBay UK matched this disc. {estimate.considered} listings were
          checked and every one was a different film, format or edition.
        </p>
      </div>
    )
  }

  // Batch X6 (#256): the value leads, as a used copy; every group eBay had is listed below it.
  const value = estimate.usedValue
  const others = estimate.segments.slice(0, 6)

  return (
    <div className="rounded-md border border-border bg-muted/40 px-3 py-2.5">
      {value ? (
        <>
          {/* One disc, so the singular of the collection's "as used copies". */}
          <p className="metadata-label">As a used copy · {estimate.basis}</p>
          <p className="mt-0.5 font-display text-2xl font-semibold text-foreground">
            {value.currency === 'GBP' ? `£${value.price}` : `${value.price} ${value.currency}`}
          </p>
          <p className="text-xs text-muted-foreground">{valueBehind({ ...value, valueBasis: value.basis })}</p>
        </>
      ) : (
        <>
          <p className="metadata-label">{estimate.basis}</p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Too few used or new listings to value it as a used copy. What eBay had:
          </p>
        </>
      )}

      {others.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-border pt-2">
          {others.map((segment) => (
            <li
              key={`${segment.formatCode}-${segment.edition}-${segment.conditionId}`}
              className="flex items-center justify-between gap-3 text-sm"
            >
              <span className="flex items-center gap-1.5 text-muted-foreground">
                {formatLabel(segment.formatCode)}
                {segment.edition === 'collector' && <Badge tone="neutral">collector</Badge>}
                <span className="text-xs">{segment.conditionLabel}</span>
              </span>
              <span className="whitespace-nowrap text-foreground">
                {money(segment)}{' '}
                <span className="text-xs text-muted-foreground">/ {segment.sampleSize}</span>
              </span>
            </li>
          ))}
        </ul>
      )}

      <p className="mt-2 text-xs text-muted-foreground">
        {estimate.matched} of {estimate.considered} listings matched this disc.
      </p>
    </div>
  )
}
