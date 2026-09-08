import { afterEach, describe, expect, it, vi } from 'vitest'
import { ZodError } from 'zod'

import { fetchCandidates, fetchMovies, formatLabel } from './api'

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

describe('formatLabel', () => {
  it('uses the live Batch 4 format vocabulary', () => {
    expect(formatLabel('4k_uhd')).toBe('4K UHD')
    expect(formatLabel('blu_ray')).toBe('Blu-ray')
    expect(formatLabel('download')).toBe('Digital')
  })
})

