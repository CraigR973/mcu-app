import { describe, expect, it } from 'vitest'
import type { CinemaTrip, NeedsYouTripItem } from '@mcu/shared'

import { detailFixture, ODEON, showingFixture, VUE } from '../pages/cinema-films-fixture'
import { ApiError, NetworkError } from './api'
import {
  flagWords,
  nextTripWords,
  pickableTimes,
  REPLY_LABELS,
  TRIP_OFFLINE,
  tripClock,
  tripErrorMessage,
  tripIsSooner,
  tripLine,
  tripNeedsYouCopy,
  tripPath,
  tripsForFilm,
  tripTally,
  tripWhen,
} from './cinema-trips'

// AC5 (#345): the worked example, Wild Horse Nine on Mon 9 Nov at 20:10 at ODEON Glasgow Quay.
const MONDAY = '2026-11-09T20:10:00Z'
const id = '0a3282b1-50db-4af9-8d94-513dc8dd4bc3'

describe('a trip in words', () => {
  it('writes the time in the cinema’s own clock, as the push does', () => {
    expect(tripWhen(MONDAY)).toBe('Mon 9 Nov 20:10')
    expect(tripClock('2026-11-10T20:00:00Z', ['IMAX'])).toBe('20:00 IMAX')
    expect(tripClock('2026-11-10T20:00:00Z', ['Format.Projection.Digital'])).toBe('20:00')
    // British Summer Time: 19:00 UTC is 20:00 at the cinema.
    expect(tripClock('2026-07-01T19:00:00Z')).toBe('20:00')
    expect(tripLine({ startsAtUtc: MONDAY, formats: [], venueName: 'ODEON Glasgow Quay' })).toBe('Mon 9 Nov · 20:10 · ODEON Glasgow Quay')
    expect(tripPath(id)).toBe(`/movie-night/trips/${id}`)
  })

  it('says each reply, and counts the proposer as going', () => {
    expect(REPLY_LABELS.invited).toBe('No reply yet')
    expect(tripTally({ going: 1, notGoing: 0, anotherTime: 0, invited: 1 })).toBe('1 going · 1 no reply yet')
    expect(tripTally({ going: 2, notGoing: 1, anotherTime: 1, invited: 0 })).toBe('2 going · 1 not going · 1 another time')
  })

  it('says what the live programme says about the time, and asks the proposer to act only when it is gone', () => {
    expect(flagWords('unconfirmed', 'ODEON Glasgow Quay')).toEqual({ line: 'Not on ODEON Glasgow Quay’s latest listing. It may have been withdrawn.', ask: null })
    expect(flagWords('withdrawn', 'ODEON Glasgow Quay')).toEqual({ line: 'ODEON Glasgow Quay no longer lists this time.', ask: 'Pick another time or cancel.' })
    expect(flagWords('cancelled', 'ODEON Glasgow Quay')).toEqual({ line: 'ODEON Glasgow Quay has cancelled this showing.', ask: 'Pick another time or cancel.' })
  })

  it('words each Needs you item and opens the trip', () => {
    const base: NeedsYouTripItem = {
      kind: 'tripInvite', tripId: id, filmTitle: 'Wild Horse Nine', posterPath: null, venueName: 'ODEON Glasgow Quay',
      venueTimezone: 'Europe/London', startsAtUtc: MONDAY, proposerName: 'Craig', fromName: null, flag: null,
    }
    expect(tripNeedsYouCopy(base)).toEqual({ title: 'Craig invited you: Wild Horse Nine, Mon 9 Nov 20:10', detail: 'ODEON Glasgow Quay', to: tripPath(id) })
    expect(tripNeedsYouCopy({ ...base, kind: 'tripSuggestion', fromName: 'Mark' }).title).toBe('Mark suggests another time for Wild Horse Nine')
    expect(tripNeedsYouCopy({ ...base, kind: 'tripWithdrawn', flag: 'withdrawn' })).toEqual({
      title: 'ODEON Glasgow Quay no longer lists your Wild Horse Nine time', detail: 'Pick another time or cancel.', to: tripPath(id),
    })
  })

  it('writes Home’s top slot, and gives it to the trip only when the trip is sooner', () => {
    const trip = { tripId: id, filmTitle: 'Wild Horse Nine', venueName: 'ODEON Glasgow Quay', venueTimezone: 'Europe/London', startsAtUtc: MONDAY, withNames: ['Mark'] }
    expect(nextTripWords(trip).sentence).toBe('Next: Wild Horse Nine, Mon 9 Nov 20:10 at ODEON Glasgow Quay, with Mark')
    expect(nextTripWords({ ...trip, withNames: [] }).detail).toBe('Mon 9 Nov 20:10 at ODEON Glasgow Quay')
    const screening = (plannedStart: string) => ({ sessionId: id, plannedStart, withNames: [], matchTitle: null })
    expect(tripIsSooner(trip, null)).toBe(true)
    expect(tripIsSooner(trip, screening('2026-11-10T19:00:00Z'))).toBe(true)
    expect(tripIsSooner(trip, screening('2026-11-09T19:00:00Z'))).toBe(false)
    expect(tripIsSooner(null, null)).toBe(false)
  })

  it('says a write offline is for when there is signal, and keeps the API’s own refusal', () => {
    expect(tripErrorMessage(new NetworkError('You are offline.', false), 'x')).toBe(TRIP_OFFLINE)
    expect(tripErrorMessage(new ApiError('The trip has moved. Check the new time and reply again.', 409), 'x'))
      .toBe('The trip has moved. Check the new time and reply again.')
  })
})

describe('the times a trip can take', () => {
  it('are the page’s confirmed times still to start, by day then cinema, less the one excluded', () => {
    const detail = detailFixture()
    detail.showings.push(
      showingFixture(4, VUE, '2026-11-04T19:00:00Z', { confirmation: 'unconfirmed' }),
      showingFixture(5, ODEON, '2026-11-03T16:00:00Z'),
    )
    const now = Date.parse('2026-11-03T17:00:00Z')
    const days = pickableTimes(detail, now, detail.showings[1]?.id)
    expect(days.map(({ day, cinemas }) => [day, cinemas.map(({ venue, showings }) => [venue.id, showings.map((s) => s.id)])])).toEqual([
      ['2026-11-03', [[VUE, [detail.showings[0]?.id]]]],
      ['2026-11-04', [[ODEON, [detail.showings[2]?.id]]]],
    ])
  })

  it('a film page lists the trips proposed on it, or at one of its showings', () => {
    const trip = (filmKey: string, showingId: string | null) => ({ filmKey, showing: { showingId } }) as unknown as CinemaTrip
    const own = trip('tmdb-1417', null)
    const listed = trip(`listing-${id}`, 'showing-1')
    const elsewhere = trip('tmdb-2001', 'showing-9')
    expect(tripsForFilm([own, listed, elsewhere], 'tmdb-1417', new Set(['showing-1']))).toEqual([own, listed])
  })
})
