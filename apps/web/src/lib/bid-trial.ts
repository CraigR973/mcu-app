import type { BidTrial, TrialSummary } from '@/lib/api'
import { formatShortDate } from '@/lib/utils'

/** "1 film", "3 films". */
export function plural(count: number, one: string, many = `${one}s`): string {
  return `${new Intl.NumberFormat('en-GB').format(count)} ${count === 1 ? one : many}`
}

/** A total to the pound, as the value panel shows one: "£412". */
export function wholePounds(total: string, currency: string): string {
  return new Intl.NumberFormat('en-GB', { style: 'currency', currency, maximumFractionDigits: 0 }).format(
    Number(total),
  )
}

export interface TrialLine {
  label: string
  text: string
}

/**
 * The report's answers for one format, in the order snag 2 asked them (V6's criteria): which
 * films bids can price, bids against asking, how many auctions end soon, and whether auctions
 * cost Buy It Now listings their places.
 */
export function summaryLines(summary: TrialSummary, minSample: number, hours: number): TrialLine[] {
  const lines: TrialLine[] = [
    {
      label: 'Bid prices',
      text: `${String(summary.withBids)} of ${plural(summary.films, 'film')} had ${String(minSample)} or more auctions with bids.`,
    },
    {
      label: 'Bids against asking',
      text:
        summary.bidToAskingPercent === null
          ? 'No film had both a bid price and an asking price.'
          : `Bids were ${String(summary.bidToAskingPercent)}% of the asking price (the median of ${plural(summary.compared, 'film')}).`,
    },
  ]
  if (summary.auctionsCounted > 0) {
    lines.push({
      label: `Ending within ${String(hours)} hours`,
      text: `${String(summary.endingSoon)} of their ${plural(summary.auctionsCounted, 'auction')}. Counting only those, ${plural(summary.withBidsEndingSoon, 'film')} would keep a bid price.`,
    })
  }
  lines.push({
    label: 'Sharing the 200 results',
    text:
      summary.cut === 0
        ? 'No search had more than 200 results, so auctions cost no Buy It Now listings.'
        : `${plural(summary.cut, 'search', 'searches')} had more than 200 results; auctions with no Buy It Now took ${plural(summary.auctionOnlyPlaces, 'place')} in them.`,
  })
  lines.push({
    label: 'Buy It Now listings',
    text:
      `${String(summary.askingSample)} matched today, ${String(summary.storedSample)} when the stored prices were taken.` +
      (summary.askingLost > 0
        ? ` ${plural(summary.askingLost, 'film')} fell under ${String(minSample)} and could not be priced on asking.`
        : ''),
  })
  return lines
}

/** Where the trial got to: running, finished, or stopped and why. */
export function trialStatus(trial: BidTrial): string {
  const sampled = trial.report?.sampled ?? 0
  const looked = trial.report?.films.length ?? 0
  const lookups = `${plural(trial.calls, 'eBay lookup')} of the day's ${String(trial.dailyShare)}`
  if (trial.status === 'running') return `Trying bid prices: ${String(looked)} of ${plural(sampled, 'film')} looked up.`
  const when = formatShortDate(trial.startedAt)
  if (trial.status === 'finished') return `Tried ${when}: ${plural(looked, 'film')} looked up, ${lookups}.`
  if (trial.status === 'budget_spent') {
    return `Tried ${when}: the day's share ran out after ${String(looked)} of ${plural(sampled, 'film')}, ${lookups}.`
  }
  return `Tried ${when}: it stopped early after ${String(looked)} of ${plural(sampled, 'film')}${trial.lastError ? ` (${trial.lastError})` : ''}.`
}
