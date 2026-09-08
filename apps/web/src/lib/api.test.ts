import { afterEach, describe, expect, it, vi } from 'vitest'
import { ZodError } from 'zod'

import { fetchCandidates, fetchFacets, fetchMovies, formatLabel, logWatch } from './api'

const movie = {
  id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
  title: '2001: A Space Odyssey',
  originalTitle: '2001: A Space Odyssey',
  year: 1968,
  posterPath: '/poster.jpg',
  backdropPath: '/backdrop.jpg',
  tmdbRating: 8.1,
  runtimeMinutes: 149,
  bestFormatOwned: '4k_uhd',
  bestHdrOwned: null,
  bestAudioOwned: null,
  identified: true,
  copyCount: 1,
  locations: [{ section: 'Front', shelf: '2nd', label: 'Front 2nd' }],
  watched: false,
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('collection API parsing', () => {
  it('sends camel-case filters and parses the shared page schema', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [movie],
      totalMovies: 1843,
      totalItems: 1857,
      page: 2,
      perPage: 60,
      pages: 31,
    })))
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchMovies({ genreId: 18, format: '4k_uhd' }, 2)

    expect(result.items[0].title).toBe('2001: A Space Odyssey')
    expect(result.totalItems).toBe(1857)
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/movies?page=2&perPage=60&genreId=18&format=4k_uhd'),
      expect.any(Object),
    )
  })

  it('rejects a successful response whose wire shape drifted', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      data: [movie],
      meta: { total: 1 },
    }))))

    await expect(fetchMovies()).rejects.toBeInstanceOf(ZodError)
  })

  it('parses candidate posters, years and overviews', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      movieId: movie.id,
      title: 'French Connection',
      query: 'The French Connection',
      candidates: [{
        tmdbId: 1051,
        title: 'The French Connection',
        year: 1971,
        overview: 'A detective pursues a drug shipment.',
        posterPath: '/candidate.jpg',
        confidence: 0.9,
        titleSimilarity: 0.9,
      }],
    }))))

    const result = await fetchCandidates(movie.id, 'The French Connection')

    expect(result.candidates[0]).toMatchObject({ tmdbId: 1051, year: 1971 })
  })
})

describe('Batch 6 location, facet and watch-log calls', () => {
  it('sends every location and facet filter as a camel-case query param', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [movie],
      totalMovies: 1,
      totalItems: 1,
      page: 1,
      perPage: 60,
      pages: 1,
    })))
    vi.stubGlobal('fetch', fetchMock)

    await fetchMovies({
      section: 'Front',
      shelf: '2nd',
      decadeFrom: 1940,
      decadeTo: 1950,
      minRating: 7,
      watched: false,
    })

    const url = String(fetchMock.mock.calls[0][0])
    expect(url).toContain('section=Front')
    expect(url).toContain('shelf=2nd')
    expect(url).toContain('decadeFrom=1940')
    expect(url).toContain('decadeTo=1950')
    expect(url).toContain('minRating=7')
    // `watched=false` is a real filter — "what have I not seen?" — and a truthiness
    // check would drop it silently.
    expect(url).toContain('watched=false')
  })

  it('parses the facet vocabulary the pickers are built from', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      sections: [
        { section: 'Front', movieCount: 550, itemCount: 550, shelves: [
          { shelf: '2nd', movieCount: 119, itemCount: 119 },
        ] },
      ],
      unsectionedItemCount: 2,
      decades: [{ decade: 1940, movieCount: 203 }],
      undatedMovieCount: 757,
    }))))

    const facets = await fetchFacets()

    expect(facets.sections[0].shelves[0].shelf).toBe('2nd')
    expect(facets.decades[0].decade).toBe(1940)
  })

  it('rejects a watch-log response whose rating left the half-star scale', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: '5c9a1f7e-1f5e-4a7b-9a1e-0c2b3d4e5f60',
      movieId: movie.id,
      movieTitle: movie.title,
      posterPath: null,
      watchedAt: '2026-09-08',
      isRewatch: false,
      personalRating: 8,
      review: null,
    }))))

    await expect(logWatch({ movieId: movie.id })).rejects.toBeInstanceOf(ZodError)
  })
})

describe('formatLabel', () => {
  it('uses the live Batch 4 format vocabulary', () => {
    expect(formatLabel('4k_uhd')).toBe('4K UHD')
    expect(formatLabel('blu_ray')).toBe('Blu-ray')
    expect(formatLabel('download')).toBe('Digital')
  })
})

