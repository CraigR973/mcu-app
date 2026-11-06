import { describe, expect, it } from 'vitest'

import { CINEMA_NOW, filmsFixture } from '@/pages/cinema-films-fixture'
import { CALENDAR_TYPES, discFilter, readMonth, showingAtCinemas, unmatchedListings } from './releases'

describe('Releases’ two calendars (AC7)', () => {
  it('reads discs and sales on one calendar and cinema dates on the other, and nothing else on either', () => {
    expect(CALENDAR_TYPES.disc).toEqual(['4k_uhd_release', 'blu_ray_release', 'sale_event'])
    expect(CALENDAR_TYPES.cinema).toEqual(['theatrical'])
  })

  it('knows a cinema release is showing by its TMDB id, with the cinemas it is at', () => {
    const showing = showingAtCinemas(filmsFixture(), CINEMA_NOW)
    expect(showing.get(1417)).toEqual({ key: 'tmdb-1417', venues: 2 })
    expect(showing.get(2001)).toEqual({ key: 'tmdb-2001', venues: 1 })
    // Listings and events are never a film to link to, whatever their title.
    expect([...showing.keys()].sort()).toEqual([1417, 2001, 2002])
  })

  it('stops linking a film once its last showing has started, and an AB6 link with no TMDB id never links', () => {
    const data = filmsFixture()
    expect(showingAtCinemas(data, Date.parse('2026-11-05T19:30:00Z')).has(2001)).toBe(false)
    data.films[2] = { ...data.films[2], key: `listing-00000000-0000-4000-8000-000000000099`, tmdbId: null }
    expect(showingAtCinemas(data, CINEMA_NOW).has(2002)).toBe(false)
    expect(showingAtCinemas(undefined, CINEMA_NOW).size).toBe(0)
  })

  it('counts the listings not matched to a film yet that are still to show', () => {
    expect(unmatchedListings(filmsFixture(), CINEMA_NOW)).toBe(2)
    expect(unmatchedListings(filmsFixture(), Date.parse('2026-11-03T22:30:00Z'))).toBe(1)
    expect(unmatchedListings(undefined, CINEMA_NOW)).toBe(0)
  })

  it('takes a month and a disc filter from the address only when they are real', () => {
    expect(readMonth('2026-12')).toBe('2026-12')
    for (const bad of [null, '', '2026-13', '2026-00', '0000-01', '9999-01', '2026-1', 'december']) expect(readMonth(bad), String(bad)).toBeNull()
    expect(discFilter('sales')).toBe('sales')
    expect(discFilter('dvd')).toBe('all')
    expect(discFilter(null)).toBe('all')
  })
})
