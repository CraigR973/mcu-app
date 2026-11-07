import type { CinemaTrip } from '@mcu/shared'

import { CINEMA_NOW, detailFixture, ODEON } from './cinema-films-fixture'

export { CINEMA_NOW }
const uid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
export const TRIP = uid(700)
export const CRAIG = uid(701)
export const MARK = uid(702)
export const ALEX = uid(703)

/** AC5: Craig's trip to the film page fixture's ODEON time tonight (21:00), Mark and Alex
 *  invited, as Mark reads it unless `asCraig`. The live showing carries its ticket link. */
export function tripFixture({ asCraig = false, ...changes }: Partial<CinemaTrip> & { asCraig?: boolean } = {}): CinemaTrip {
  const detail = detailFixture()
  const live = detail.showings[1]
  const venue = detail.venues.find((item) => item.id === ODEON) ?? null
  return {
    id: TRIP,
    filmKey: detail.film.key,
    filmTitle: detail.film.title,
    posterPath: '/fav.jpg',
    proposer: { profileId: CRAIG, displayName: 'Craig', isYou: asCraig },
    status: 'upcoming',
    revision: 1,
    showing: {
      showingId: live?.id ?? null, venueId: ODEON, venueName: 'ODEON Kilmarnock', venueTimezone: 'Europe/London',
      startsAtUtc: live?.startsAtUtc ?? '2026-11-03T21:00:00Z', endsAtUtc: null, screen: null, formats: [], flag: null,
      live: live ?? null, venue,
    },
    invitees: [
      { profileId: ALEX, displayName: 'Alex', isYou: false, reply: 'invited', replyRevision: 0, repliedAtUtc: null, suggestion: null },
      { profileId: MARK, displayName: 'Mark', isYou: !asCraig, reply: 'invited', replyRevision: 0, repliedAtUtc: null, suggestion: null },
    ],
    counts: { going: 1, notGoing: 0, anotherTime: 0, invited: 2 },
    yourReply: asCraig ? null : 'invited',
    createdAtUtc: '2026-11-03T12:00:00Z',
    movedAtUtc: null,
    cancelledAtUtc: null,
    ...changes,
  }
}
