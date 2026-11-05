import { describe, expect, it } from 'vitest'
import { cinemaFixture, CINEMA_NOW } from '@/pages/cinema-test-fixture'
import { filmsFixture, ODEON } from '@/pages/cinema-films-fixture'
import { cinemaLine, cinemaSections, clock, dayHeading, listingState, londonDate, londonTime, OFFICIAL_PROGRAMMES, programmeDays, programmeUrl, runBadge, shortDay, shortHorizons, shortVenueName, showingBooking, showingFormats, showingScreen } from './cinemas'

describe('cinema booking safety before another fetch', () => {
  it('uses UK civil dates and times across summer time regardless of the browser zone', () => {
    expect(londonDate(Date.parse('2026-06-01T23:30:00Z'))).toBe('2026-06-02')
    expect(londonTime('2026-06-01T23:30:00Z')).toContain('00:30')
    expect(londonTime('2026-09-23T12:00:00Z')).toContain('23 Sep')
    expect(londonTime('invalid')).toBe('invalid')
  })
  it.each(['javascript:alert(1)', 'http://www.myvue.com/cinema/x', 'https://user:pass@www.myvue.com/cinema/x', 'https://127.0.0.1/cinema/x', 'https://www.myvue.com:444/cinema/x', 'https://www.myvue.com/other/path'])('refuses unsafe or unexpected booking %s', (bookingUrl) => {
    const p = cinemaFixture(), showing = { ...p.films[0].showings[0], bookingUrl }
    expect(showingBooking(showing, p.venues[0], CINEMA_NOW, true)).toBeNull()
  })
  it('keeps official fallbacks for all nine venues without an API answer', () => {
    expect(OFFICIAL_PROGRAMMES).toHaveLength(9)
    for (const [, url] of OFFICIAL_PROGRAMMES) expect(programmeUrl(url)).toBe(url)
    expect(programmeUrl('https://example.com/')).toBeNull()
  })
  it('expires cached showing/coverage/upstream evidence and stops offline, failed or started bookings', () => {
    const p = cinemaFixture(), s = p.films[0].showings[0], v = p.venues[0]
    expect(showingBooking(s, v, CINEMA_NOW, true)).toBe(s.bookingUrl)
    expect(showingBooking(s, v, CINEMA_NOW, false)).toBeNull()
    expect(showingBooking(s, v, CINEMA_NOW + 30 * 3600000, true)).toBeNull()
    expect(showingBooking({ ...s, confirmation: 'unconfirmed' }, v, CINEMA_NOW, true)).toBeNull()
    expect(showingBooking({ ...s, startsAtUtc: '2026-11-03T16:00:00Z' }, v, CINEMA_NOW, true)).toBeNull()
    expect(showingBooking(s, { ...v, coverage: [{ ...v.coverage[0], status: 'failed' }] }, CINEMA_NOW, true)).toBeNull()
    expect(showingBooking(s, { ...v, coverage: [{ ...v.coverage[0], upstreamUtc: '2026-11-01T00:00:00Z' }] }, CINEMA_NOW, true)).toBeNull()
    expect(showingBooking(s, { ...v, coverage: [{ ...v.coverage[0], lastSuccessUtc: '2026-11-01T00:00:00Z' }] }, CINEMA_NOW, true)).toBeNull()
  })
})

describe('human programme labels from observed source fields', () => {
  it('decodes the observed projection enums and labels an unknown enum without guessing', () => {
    expect(showingFormats(['3d', 'Format.Projection.3d', 'Format.Projection.4k', 'Format.Projection.Digital', 'Format.Projection.Imax', 'IMAX', 'imax', 'isense', 'Format.Future.Unknown'])).toEqual(['3D', '4K', 'Digital projection', 'IMAX', 'iSense', 'Format unverified'])
  })
  it('names numeric screens without repeating an existing label or changing a named auditorium', () => {
    expect(['2', 'Screen 2', 'Studio'].map(showingScreen)).toEqual(['Screen 2', 'Screen 2', 'Studio'])
  })
})

describe('At the cinema’s film-first reading (AC4)', () => {
  const all = { run: 'all' as const, day: null, venueIds: null }
  it('labels days, times and runs the way a phone has room for', () => {
    expect(shortDay('2026-11-03', '2026-11-03')).toBe('Today')
    expect(shortDay('2026-11-04', '2026-11-03')).toBe('Tomorrow')
    expect(shortDay('2026-11-08', '2026-11-03')).toBe('Sun 8')
    expect(dayHeading('2026-11-03', '2026-11-03')).toBe('Today · Tue 3 Nov')
    expect(dayHeading('2026-11-29', '2026-11-03')).toBe('Sun 29 Nov')
    expect(clock('2026-06-01T18:30:00Z')).toBe('19:30')
    expect(runBadge('newRelease', 'UK release 23 Oct 2026 · first run')).toBe('First run')
    expect(runBadge('newRelease', 'UK release 7 Nov 2026 · preview')).toBe('Preview')
    expect(runBadge('olderFilm', 'UK release 1977 · rerun')).toBe('Rerun')
    expect(runBadge('olderFilm', null)).toBe('Rerun')
    expect(runBadge('unclassified', 'UK release 1 Jun 2026 · between first run and rerun')).toBeNull()
  })
  it('sorts this week widest first, coming up soonest first, and listings by title', () => {
    const sections = cinemaSections(filmsFixture(), all, CINEMA_NOW)
    expect(sections.thisWeek.map((line) => line.card.title)).toEqual(['A returning favourite', 'A current first run'])
    expect(sections.comingUp.map((line) => line.card.title)).toEqual(['Opening later'])
    expect(sections.listings.map((line) => line.card.title)).toEqual(['An uncertain programme', 'Waiting film'])
    expect(sections.events.map((line) => line.card.title)).toEqual(['NT Live: Hamlet'])
    expect(sections.counts).toEqual({ all: 6, newRelease: 2, olderFilm: 1, unclassified: 3 })
  })
  it('counts runs after the day and cinema, and reads a card’s next showing from what is left', () => {
    const odeonOnly = cinemaSections(filmsFixture(), { ...all, venueIds: [ODEON] }, CINEMA_NOW)
    expect(odeonOnly.counts).toEqual({ all: 5, newRelease: 2, olderFilm: 1, unclassified: 2 })
    // One cinema and one showing each now, so the title decides the order.
    expect(odeonOnly.thisWeek.map((line) => line.card.title)).toEqual(['A current first run', 'A returning favourite'])
    const favourite = odeonOnly.thisWeek[1]
    expect([favourite.card.title, favourite.venueIds, favourite.next.at]).toEqual(['A returning favourite', [ODEON], '2026-11-03T21:00:00Z'])
    const later = cinemaLine(filmsFixture().films[0], all, Date.parse('2026-11-03T20:30:00Z'))
    expect(later?.showings).toBe(1)
    expect(cinemaLine(filmsFixture().films[0], all, Date.parse('2026-11-03T21:30:00Z'))).toBeNull()
  })
  it('names the cinemas that list less than the fortnight, and the days showings fall on', () => {
    const data = filmsFixture()
    expect(shortHorizons(data).to.map(({ day, venues }) => [day, venues.map((venue) => venue.slug)])).toEqual([
      ['2026-11-04', ['vue-st-enoch']],
      ['2026-11-09', ['odeon-kilmarnock']],
    ])
    data.venues[0].coverage = data.venues[0].coverage.map((day) => ({ ...day, observed: false, status: 'failed' }))
    expect(shortHorizons(data).none.map((venue) => venue.slug)).toEqual(['vue-st-enoch'])
    expect(programmeDays(filmsFixture(), CINEMA_NOW)).toEqual(['2026-11-03', '2026-11-04', '2026-11-05', '2026-11-06', '2026-11-12'])
  })
  it('says what a listing is where a film would say its run', () => {
    expect(listingState({ kind: 'event', identityStatus: 'event' })).toBe('Event or double bill')
    expect(listingState({ kind: 'listing', identityStatus: 'review' })).toBe('Waiting for a check')
    expect(listingState({ kind: 'listing', identityStatus: 'conflict' })).toBe('Title differs — check cinema')
    expect(listingState({ kind: 'listing', identityStatus: 'unverified' })).toBe('Not matched yet')
    expect(shortVenueName({ slug: 'gft', name: 'Glasgow Film Theatre' })).toBe('GFT')
    expect(shortVenueName({ slug: 'new-venue', name: 'A New Venue' })).toBe('A New Venue')
  })
})
