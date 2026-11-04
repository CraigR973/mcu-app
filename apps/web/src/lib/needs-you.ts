import type { NeedsYouItem } from '@mcu/shared'

import { formatDayMonth } from './utils'

function days(count: number): string {
  return `${String(count)} day${count === 1 ? '' : 's'}`
}

/**
 * One item in words, and the exact place that acts on it — AC1 (#335).
 *
 * Every destination is Loans with the copy's row picked out, so the confirm flow there,
 * including choosing another shelf, is the only way anything changes.
 */
export function needsYouCopy(item: NeedsYouItem): { title: string; detail: string; to: string } {
  const to = `/loans?view=${item.kind === 'putBack' ? 'back' : 'open'}&loan=${item.loanId}`
  if (item.kind === 'putBack') {
    const where = item.locationLabel === 'Unfiled' ? 'choose a shelf' : `goes to ${item.locationLabel}`
    const when = item.returnedDate ? `Returned ${formatDayMonth(item.returnedDate)} · ` : ''
    return { title: `Put back ${item.movieTitle}`, detail: `${when}${where}`, to }
  }
  if (item.kind === 'handOver') {
    const by = item.neededBy ? ` · needed by ${formatDayMonth(item.neededBy)}` : ''
    return { title: `Hand over ${item.movieTitle}`, detail: `${item.borrowerName} asked for it${by}`, to }
  }
  const timing = item.daysOverdue !== null
    ? `${days(item.daysOverdue)} overdue`
    : `out ${days(item.daysOut ?? 0)}, no due date`
  const since = item.lentDate ? formatDayMonth(item.lentDate) : null
  if (item.borrowerIsYou) {
    return {
      title: `Give back ${item.movieTitle}`,
      detail: since ? `You've had it since ${since} · ${timing}` : `You have it · ${timing}`,
      to,
    }
  }
  return {
    title: `Ask ${item.borrowerName} for ${item.movieTitle}`,
    detail: since ? `Lent ${since} · ${timing}` : timing,
    to,
  }
}
