import { ExternalLink } from 'lucide-react'

import type { CopyValuation } from '@/lib/api'
import { formatShortDate } from '@/lib/utils'

import { valueBehind } from './value-words'

function money(valuation: CopyValuation & { price: string }): string {
  return valuation.currency === 'GBP' ? `£${valuation.price}` : `${valuation.price} ${valuation.currency}`
}

function listings(count: number, kind: string): string {
  return `${String(count)} ${kind} ${count === 1 ? 'listing' : 'listings'}`
}

/**
 * A disc's stored value from the last valuation run — Batch T6, as a used copy since X6.
 *
 * Shown beside the live "What is it worth?" check, and in the same terms: what a used copy
 * of the disc is being **asked** for on eBay (`DECISIONS.md` #256), with the listings behind
 * it, their range and the date it was checked. A disc with too few listings says so, rather
 * than showing a guess.
 */
export function StoredValue({ valuation }: { valuation: CopyValuation }) {
  const checked = formatShortDate(valuation.checkedAt)
  if (valuation.status === 'not_priced' || valuation.price === null) {
    const found =
      valuation.usedCount === 0 && valuation.newCount === 0
        ? 'no matching listings'
        : `${listings(valuation.usedCount, 'used')} and ${listings(valuation.newCount, 'new')}`
    return (
      <div>
        <p className="text-sm leading-6 text-muted-foreground">
          Not priced when checked on {checked}: eBay had {found}, and a value needs at least{' '}
          {valuation.minSample} of one kind.
        </p>
        <SoldListingsLink url={valuation.soldListingsUrl} />
      </div>
    )
  }
  const behind =
    valuation.valueBasis && valuation.low && valuation.high
      ? valueBehind({
          valueBasis: valuation.valueBasis,
          sampleSize: valuation.sampleSize,
          low: valuation.low,
          high: valuation.high,
          factor: valuation.factor,
        })
      : // Every priced value since X6 carries these; the API serves no older one.
        `median of ${String(valuation.sampleSize)} listings`
  return (
    <div>
      {/* One disc, so the singular of the collection's "as used copies". */}
      <p className="metadata-label">Last valued as a used copy · {valuation.basis}</p>
      <p className="mt-0.5 font-display text-xl font-semibold text-foreground">{money({ ...valuation, price: valuation.price })}</p>
      <p className="text-xs text-muted-foreground">
        {behind} · checked {checked}
      </p>
      <SoldListingsLink url={valuation.soldListingsUrl} />
    </div>
  )
}

/**
 * Batch V8: what the film actually sold for on eBay, which the app cannot read (sold
 * listings are closed to apps). It opens in the person's own browser, where eBay asks them
 * to sign in.
 */
function SoldListingsLink({ url }: { url: string | null }) {
  if (!url) return null
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
    >
      Sold listings on eBay <ExternalLink className="h-3 w-3" aria-hidden />
    </a>
  )
}
