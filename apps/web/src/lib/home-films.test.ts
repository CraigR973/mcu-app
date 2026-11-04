import { describe, expect, it } from 'vitest'

import type { CalendarEntry, Highlights, OnThisDayMemory, RewatchSuggestion } from './api'
import { HomeFilms, homeLineup } from './home-films'

const id = (n: number) => `3f2504e0-4f89-41d3-9a0c-0305e82c${String(3400 + n)}`

function rewatch(n: number, title: string): RewatchSuggestion {
  return { movieId: id(n), movieTitle: title, posterPath: null, lastWatchedAt: '2024-03-19', personalRating: 5 }
}

function memory(n: number, title: string): OnThisDayMemory {
  return { id: id(90 + n), movieId: id(n), movieTitle: title, posterPath: null, watchedAt: '2024-11-04', yearsAgo: 2, personalRating: null }
}

function release(n: number, title: string, movieId: string | null): CalendarEntry {
  return { id: id(50 + n), title, releaseType: '4k_uhd_release', typeLabel: '4K UHD', releaseDate: '2026-11-09', label: null, region: 'GB', url: null, posterPath: null, overview: null, movieId }
}

const film = (n: number, title: string) => ({ movieId: id(n), title, year: 1975, posterPath: null })

function highlights(over: Partial<Highlights> = {}): Highlights {
  return {
    topRated: { items: [], ratedBy: [], notRatedBy: [] },
    mostRewatched: [],
    mostValuable: [],
    bestReviewed: [],
    ...over,
  }
}

describe('HomeFilms — AC2, no film twice on Home', () => {
  it('takes each film once, in page order, and lets a film with no key through', () => {
    const films = new HomeFilms()
    expect(films.take(['a', 'b'], (key) => key)).toEqual(['a', 'b'])
    expect(films.take(['b', 'c', null], (key) => key)).toEqual(['c', null])
    expect(films.take([null, null], (key) => key)).toEqual([null, null])
  })

  it('peeks without claiming, then claims what was shown', () => {
    const films = new HomeFilms()
    films.take(['a'], (key) => key)
    expect(films.peek(['a', 'b'], (key) => key)).toEqual(['b'])
    expect(films.peek(['b', 'c'], (key) => key)).toEqual(['b', 'c'])
    films.claim(['b', 'c'])
    expect(films.take(['b', 'c', 'd'], (key) => key)).toEqual(['d'])
  })
})

describe('homeLineup — AC2 (#337)', () => {
  it('features the first film worth a rewatch, and nobody else shows it', () => {
    const lineup = homeLineup({
      rewatch: [rewatch(1, 'Double Indemnity'), rewatch(2, 'The Maltese Falcon')],
      highlights: highlights({
        mostRewatched: [{ ...film(1, 'Double Indemnity'), viewings: 7, byPerson: [] }, { ...film(3, 'Jaws'), viewings: 7, byPerson: [] }],
        bestReviewed: [{ ...film(1, 'Double Indemnity'), overall: 4.5, outOf: 5, formatCode: '4k_uhd', strength: 'picture', scores: [] }],
      }),
      onThisDay: [memory(3, 'Jaws'), memory(4, 'Zodiac')],
      calendar: [release(1, 'Fargo', id(5)), release(2, 'A film nobody owns', null)],
    })
    expect(lineup.featured).toMatchObject({ movieId: id(1), eyebrow: 'Worth a rewatch' })
    expect(lineup.featured?.detail).toBe('You gave it ★ 5 and last saw it on 19 Mar 2024.')
    expect(lineup.discs.map((entry) => entry.title)).toEqual(['Fargo', 'A film nobody owns'])
    expect(lineup.highlights?.mostRewatched.map((f) => f.title)).toEqual(['Jaws'])
    expect(lineup.highlights?.bestReviewed).toEqual([])
    // Jaws is in Highlights, so On this day gives way; Falcon is still unseen on the page.
    expect(lineup.forYou.map((f) => f.title)).toEqual(['Zodiac', 'The Maltese Falcon'])
    expect(lineup.forYou[1]?.detail).toBe('Last seen Mar 2024')
  })

  it('falls back to the most rewatched, then to nothing', () => {
    const most = homeLineup({ rewatch: [], highlights: highlights({ mostRewatched: [{ ...film(3, 'Jaws'), viewings: 7, byPerson: [] }] }) })
    expect(most.featured).toMatchObject({ movieId: id(3), eyebrow: 'Most rewatched', detail: '7 viewings across both diaries.' })
    expect(most.highlights?.mostRewatched).toEqual([])
    expect(homeLineup({}).featured).toBeNull()
    expect(homeLineup({}).highlights).toBeNull()
  })

  it('lets one film sit in two Highlights tabs, only one of which shows at a time', () => {
    const lineup = homeLineup({
      highlights: highlights({
        mostRewatched: [{ ...film(1, 'Alien'), viewings: 3, byPerson: [] }, { ...film(2, 'Heat'), viewings: 3, byPerson: [] }],
        bestReviewed: [{ ...film(2, 'Heat'), overall: 4, outOf: 5, formatCode: 'blu_ray', strength: 'sound', scores: [] }],
      }),
      rewatch: [rewatch(2, 'Heat')],
    })
    // Heat is featured; Alien heads Most rewatched; Best discs had only Heat.
    expect(lineup.featured?.movieId).toBe(id(2))
    expect(lineup.highlights?.mostRewatched.map((f) => f.title)).toEqual(['Alien'])
    expect(lineup.highlights?.bestReviewed).toEqual([])
    expect(lineup.forYou).toEqual([])
  })
})
