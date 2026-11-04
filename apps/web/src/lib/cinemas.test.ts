import { describe, expect, it } from 'vitest'
import { cinemaFixture, CINEMA_NOW } from '@/pages/cinema-test-fixture'
import { londonDate, londonTime, OFFICIAL_PROGRAMMES, programmeUrl, showingBooking, showingFormats, showingScreen } from './cinemas'

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
