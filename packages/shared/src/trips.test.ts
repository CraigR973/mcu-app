import { describe, expect, it } from 'vitest'
import { cinemaTripListSchema, cinemaTripSchema, invitablePeopleSchema, needsYouSchema, reminderRunSchema } from './schemas'

// AC5 (#345): cinema trips, and the two fields they add to Needs you.
const id = '0a3282b1-50db-4af9-8d94-513dc8dd4bc3'
const other = '5d2f8e8c-7a31-4c51-9f67-2f1d1e9b6c0a'
const live = {
  id, venueId: id, sourceTitle: 'Wild Horse Nine', startsAtUtc: '2026-11-09T20:10:00Z',
  endsAtUtc: null, screen: '4', formats: ['Format.Projection.Digital'], releaseCategory: 'newRelease',
  categoryConfidence: 'verified', categoryEvidence: { sourceUrl: null, description: 'UK release 30 Oct 2026 · first run' },
  categoryReason: 'UK release 30 Oct 2026 · first run', sourceReleaseDate: null, reissue: null,
  confirmation: 'confirmed', lastSeenUtc: '2026-11-09T07:00:00Z', observationStale: false,
  upstreamAge: 'unknown', bookingUrl: 'https://www.odeon.co.uk/ticketing/seat-picker/?showtimeId=1',
}
const venue = {
  id, slug: 'odeon-glasgow-quay', name: 'ODEON Glasgow Quay', source: 'cinematimes',
  sourceUrl: 'https://cinematimes.com/uk/glasgow/cinemas/odeon-glasgow-springfield-quay/',
  officialUrl: 'https://www.odeon.co.uk/cinemas/glasgow-quay/', collectionEnabled: true,
  coverage: [{ localDate: '2026-11-09', status: 'healthy', observed: true, complete: true,
    lastAttemptUtc: '2026-11-09T07:00:00Z', lastSuccessUtc: '2026-11-09T07:00:00Z',
    sourceUpdateLabel: null, upstreamUtc: null, upstreamAge: 'unknown', error: null }],
}
const trip = {
  id, filmKey: 'tmdb-891621', filmTitle: 'Wild Horse Nine', posterPath: '/whn.jpg',
  proposer: { profileId: id, displayName: 'Craig', isYou: false },
  status: 'upcoming', revision: 2,
  showing: {
    showingId: id, venueId: id, venueName: 'ODEON Glasgow Quay', venueTimezone: 'Europe/London',
    startsAtUtc: '2026-11-09T20:10:00Z', endsAtUtc: null, screen: '4', formats: [], flag: null, live, venue,
  },
  invitees: [
    { profileId: other, displayName: 'Mark', isYou: true, reply: 'anotherTime', replyRevision: 3,
      repliedAtUtc: '2026-11-09T08:00:00Z',
      suggestion: { showingId: null, venueName: 'Cineworld Glasgow Silverburn', startsAtUtc: '2026-11-10T20:00:00Z',
        formats: ['IMAX'], flag: 'withdrawn' } },
  ],
  counts: { going: 1, notGoing: 0, anotherTime: 1, invited: 0 },
  yourReply: 'anotherTime', createdAtUtc: '2026-11-08T18:00:00Z', movedAtUtc: '2026-11-09T07:30:00Z',
  cancelledAtUtc: null,
}

describe('a cinema trip', () => {
  it('reads every reply, the suggestion and the live showing as the API sends them', () => {
    expect(cinemaTripSchema.parse(trip)).toEqual(trip)
    expect(cinemaTripListSchema.parse({ upcoming: [trip], past: [] }).upcoming).toHaveLength(1)
  })

  it('reads a showing the programme no longer lists: no live row, no venue', () => {
    const { live: _live, venue: _venue, ...snapshot } = trip.showing
    const parsed = cinemaTripSchema.parse({ ...trip, showing: { ...snapshot, flag: 'withdrawn' } })
    expect(parsed.showing.live).toBeNull()
    expect(parsed.showing.venue).toBeNull()
  })

  it.each(['unconfirmed', 'withdrawn', 'cancelled'])('accepts the %s flag', flag => {
    expect(cinemaTripSchema.safeParse({ ...trip, showing: { ...trip.showing, flag } }).success).toBe(true)
  })

  it.each([
    ['an unknown flag', { showing: { ...trip.showing, flag: 'gone' } }],
    ['an unknown reply', { yourReply: 'maybe' }],
    ['a revision below one', { revision: 0 }],
    ['nobody going, when the proposer always is', { counts: { ...trip.counts, going: 0 } }],
    ['a film address AC4 does not give', { filmKey: 'Wild Horse Nine' }],
  ])('refuses %s', (_name, change) => {
    expect(cinemaTripSchema.safeParse({ ...trip, ...change }).success).toBe(false)
  })

  it('lists the people the reader can invite', () => {
    const people = { people: [{ profileId: other, displayName: 'Mark', isYou: false }] }
    expect(invitablePeopleSchema.parse(people)).toEqual(people)
  })
})

describe('Needs you, with trips (AC5)', () => {
  it('still reads an answer from before AC5, with no trips and no next trip', () => {
    const parsed = needsYouSchema.parse({ items: [], nextScreening: null })
    expect(parsed.trips).toEqual([])
    expect(parsed.nextTrip).toBeNull()
  })

  it('reads trip items and the next trip, defaulting what an item does not carry', () => {
    const item = {
      kind: 'tripInvite', tripId: id, filmTitle: 'Wild Horse Nine', posterPath: null,
      venueName: 'ODEON Glasgow Quay', venueTimezone: 'Europe/London',
      startsAtUtc: '2026-11-09T20:10:00Z', proposerName: 'Craig',
    }
    const parsed = needsYouSchema.parse({
      items: [], trips: [item],
      nextTrip: { tripId: id, filmTitle: 'Wild Horse Nine', venueName: 'ODEON Glasgow Quay',
        venueTimezone: 'Europe/London', startsAtUtc: '2026-11-09T20:10:00Z', withNames: ['Mark'] },
    })
    expect(parsed.trips[0]).toEqual({ ...item, fromName: null, flag: null })
    expect(parsed.nextTrip?.withNames).toEqual(['Mark'])
    expect(needsYouSchema.safeParse({ items: [], trips: [{ ...item, kind: 'tripMaybe' }] }).success).toBe(false)
  })

  it('reads a reminder pass from before AC5 as having reminded no trips', () => {
    const run = { asOf: '2026-11-09', seasonsSeeded: 0, saleEvents: 0, releases: 0, overdueLoans: 0, queued: 0, delivered: 0 }
    expect(reminderRunSchema.parse(run).cinemaTrips).toBe(0)
  })
})
