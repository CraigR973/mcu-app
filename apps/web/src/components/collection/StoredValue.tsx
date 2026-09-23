import type { CopyValuation } from '@/lib/api'
import { formatShortDate } from '@/lib/utils'

function money(valuation: CopyValuation & { price: string }): string {
  return valuation.currency === 'GBP' ? `£${valuation.price}` : `${valuation.price} ${valuation.currency}`
}

function listings(count: number, kind = ''): string {
  return `${String(count)} ${kind}${count === 1 ? 'listing' : 'listings'}`
}

/**
 * A disc's stored value from the last valuation run — Batch T6.
 *
 * Shown beside the live "What is it worth?" check, and in the same terms: the median of
 * current eBay **asking** prices, with the number of listings behind it and the date it was
 * checked. A disc with too few listings says so, rather than showing a guess.
 */
export function StoredValue({ valuation }: { valuation: CopyValuation }) {
  const checked = formatShortDate(valuation.checkedAt)
  if (valuation.status === 'not_priced' || valuation.price === null) {
    const found =
      valuation.sampleSize === 0 ? 'no matching listings' : `only ${listings(valuation.sampleSize, 'matching ')}`
    return (
      <p className="text-sm leading-6 text-muted-foreground">
        Not priced when checked on {checked}: eBay had {found}, and a price needs at least {valuation.minSample}.
      </p>
    )
  }
  return (
    <div>
      <p className="metadata-label">Last valued · {valuation.basis}</p>
      <p className="mt-0.5 font-display text-xl font-semibold text-foreground">{money({ ...valuation, price: valuation.price })}</p>
      <p className="text-xs text-muted-foreground">
        median of {listings(valuation.sampleSize)}
        {valuation.conditionLabel ? ` · ${valuation.conditionLabel}` : ''} · checked {checked}
      </p>
    </div>
  )
}
