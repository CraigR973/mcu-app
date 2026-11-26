import type { AssignedReview, NeedsYou, NeedsYouItem } from '@mcu/shared'

import { othersTripCopy, tripNeedsYouCopy } from './cinema-trips'
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

/** Another keeper's loan item, as the reader reads it (AE8): a request the reader made is the
 *  other keeper's to hand over; a disc the other keeper has is still the reader's to ask for.
 *  Since AF1 (#372) every disc to put back is Mark's, so Craig reads it as his. */
function othersLoanCopy(item: NeedsYouItem, owner: string): { title: string; detail: string; to: string } {
  const base = needsYouCopy(item)
  if (item.kind === 'putBack') return { ...base, title: `${owner} to put back ${item.movieTitle}` }
  if (item.kind !== 'handOver') return base
  const by = item.neededBy ? ` · needed by ${formatDayMonth(item.neededBy)}` : ''
  return { ...base, title: `${owner} to hand over ${item.movieTitle}`, detail: `You asked for it${by}` }
}

/** AG3 (UX54-03): whose move a review is. Until it is answered it is the person it was
 *  assigned to; once answered, or when the record has changed, it is the admin's to apply or
 *  look at again, and the person who answered has nothing left to do. */
function adminsMove(status: string): boolean {
  return status === 'answered' || status === 'changed'
}

/** One row on Home's Needs you and on the Needs you page (AE8, #355). */
export interface NeedsYouRowData {
  key: string
  /** AF1 (#372): `app` is a problem the daily check found, `note` a line sent to Craig. */
  kind: 'trip' | 'loan' | 'review' | 'app' | 'note'
  title: string
  detail: string
  /** Where the row opens; null for an App row with nowhere to open, and for a line to Craig. */
  to: string | null
  poster: string | null
  film: string
  /** "You", whose item it is, "App", or who sent a line. */
  label: string
  own: boolean
  /** AE9: whose page the label opens; null when not known, and on an App row. */
  ownerId: string | null
  /** AF1: a line to Craig, which he clears from the row. */
  noteId?: string | null
}

type Review = Pick<AssignedReview, 'id' | 'title' | 'question' | 'status'> & Partial<Pick<AssignedReview, 'assignedTo' | 'assigneeName'>>
type Reader = { id: string; displayName?: string; role?: string }

/**
 * Everything on Needs you as rows, the reader's own first — AE8 (#355). The people who keep the
 * shelves see each other's items too: each says whose it is, in its words for the reader, and
 * opens its page, where only its owner can act (loans, which both keepers act on, aside).
 *
 * AF1 (#372): Craig's app problems and the lines sent to him (`attentionRows`) come after his own
 * items and before Mark's.
 */
export function needsYouRows(
  data: { items?: NeedsYouItem[]; trips?: NeedsYou['trips']; reviews?: Review[] },
  reader: Reader | null | undefined,
  app: NeedsYouRowData[] = [],
): NeedsYouRowData[] {
  const mine = (id: string | null | undefined) => !id || id === reader?.id
  const rows: NeedsYouRowData[] = [
    ...(data.trips ?? []).map((trip) => {
      const own = mine(trip.owner?.profileId)
      const copy = own || !trip.owner ? tripNeedsYouCopy(trip) : othersTripCopy(trip, trip.owner.name, reader?.displayName)
      return { ...copy, key: `${trip.kind}:${trip.tripId}:${trip.fromName ?? ''}:${trip.owner?.profileId ?? ''}`, kind: 'trip' as const, poster: trip.posterPath, film: trip.filmTitle, label: own ? 'You' : trip.owner?.name ?? 'You', own, ownerId: trip.owner?.profileId ?? reader?.id ?? null }
    }),
    ...(data.items ?? []).map((item) => {
      const own = mine(item.owner?.profileId)
      const copy = own || !item.owner ? needsYouCopy(item) : othersLoanCopy(item, item.owner.name)
      return { ...copy, key: `${item.kind}:${item.loanId}`, kind: 'loan' as const, poster: item.posterPath, film: item.movieTitle, label: own ? 'You' : item.owner?.name ?? 'You', own, ownerId: item.owner?.profileId ?? reader?.id ?? null }
    }),
    // AG11 (#390): a resolved review is nobody's move. The API leaves it off Needs you; this
    // keeps it off should one ever arrive. AH2 (#401): so is a closed one.
    ...(data.reviews ?? []).filter((review) => review.status !== 'resolved' && review.status !== 'closed').map((review) => {
      const who = review.assigneeName ?? 'someone else'
      if (adminsMove(review.status)) {
        // AG3 (UX54-03): labelled by whose move it is, not by who answered.
        const own = reader?.role === 'admin'
        const detail = review.status === 'changed'
          ? 'Look again · the record changed since the question'
          : own ? `Apply ${who}’s answer · awaiting correction` : `${mine(review.assignedTo) ? 'You' : who} answered · waiting for the admin`
        return {
          key: `review:${review.id}`, kind: 'review' as const, title: review.title, detail,
          to: `/needs-you?review=${review.id}`, poster: null, film: review.title,
          label: own ? 'You' : 'Admin', own, ownerId: own ? reader?.id ?? null : null,
        }
      }
      const own = mine(review.assignedTo)
      return {
        key: `review:${review.id}`, kind: 'review' as const, title: review.title,
        detail: own ? review.question : `For ${who} · ${review.question}`,
        to: `/needs-you?review=${review.id}`, poster: null, film: review.title,
        label: own ? 'You' : review.assigneeName ?? 'Someone else', own,
        ownerId: review.assignedTo ?? reader?.id ?? null,
      }
    }),
  ]
  return [...rows.filter((row) => row.own), ...app, ...rows.filter((row) => !row.own)]
}

