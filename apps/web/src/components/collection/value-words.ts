import type { ValueBasis } from '@/lib/api'

/** The parts of a value as a used copy that say what stands behind it. */
export interface ValueBehind {
  valueBasis: ValueBasis
  sampleSize: number
  low: string
  high: string
  factor: string | null
}

function listings(count: number, kind: string): string {
  return `${String(count)} ${kind} ${count === 1 ? 'listing' : 'listings'}`
}

/**
 * What stands behind a disc's value as a used copy — Batch X6 (`DECISIONS.md` #256).
 *
 * The value is the median of its used listings when there are three or more; otherwise New's
 * median times the used-to-New factor measured for the format. Every surface that shows the
 * value says which, how many listings, and their range, so a value resting on four New
 * listings and a factor does not read like one resting on thirty used copies.
 *
 * `short` is for a poster card: "24 used listings, £3.29–£65.99" or "4 new listings × 0.60,
 * £7.97–£13.16". The long form leads with the rule.
 */
export function valueBehind(value: ValueBehind, { short = false }: { short?: boolean } = {}): string {
  const range = `£${value.low}–£${value.high}`
  if (value.valueBasis === 'used') {
    return short
      ? `${listings(value.sampleSize, 'used')}, ${range}`
      : `median of ${listings(value.sampleSize, 'used')}, ${range}`
  }
  const factor = value.factor ?? ''
  return short
    ? `${listings(value.sampleSize, 'new')} × ${factor}, ${range}`
    : `too few used listings: New's median × ${factor}, from ${listings(value.sampleSize, 'new')}, ${range}`
}
