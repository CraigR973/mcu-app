import { afterEach, describe, expect, it, vi } from 'vitest'
import { ZodError } from 'zod'

import {
  addCollectionItem,
  checkDuplicate,
  confirmBarcode,
  DuplicateItemError,
  fetchAudit,
  fetchCandidates,
  fetchFacets,
  fetchMovies,
  fetchOnThisDayMemories,
  fetchRewatchSuggestions,
  formatLabel,
  identifyMovie,
  logWatch,
  lookupBarcode,
  restoreCollectionItem,
  updateCollectionItem,
} from './api'

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

    expect(result.candidates[0]).toMatchObject({ tmdbId: 1051, year: 1971, mediaType: 'film' })
    // An answer from before Batch Y3 has no series, and still parses.
    expect(result.seriesCandidates).toEqual([])
  })

  it('reads TMDB series beside the films, and identifies a title as one (Batch Y3)', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        movieId: movie.id,
        title: 'Band of Brothers',
        query: 'Band of Brothers',
        candidates: [],
        seriesCandidates: [{
          tmdbId: 4613,
          mediaType: 'tv',
          title: 'Band of Brothers',
          year: 2001,
          overview: 'Easy Company.',
          posterPath: null,
          confidence: 1,
          titleSimilarity: 1,
        }],
      })))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...movie,
        identified: true,
        mediaType: 'tv',
        imdbId: 'tt0185906',
        overview: 'Easy Company.',
        tagline: null,
        genres: [],
        cast: [],
        crew: [],
        trailerKey: null,
        letterboxdSlug: null,
        reviews: [],
      })))
    vi.stubGlobal('fetch', fetchMock)

    const offered = await fetchCandidates(movie.id)
    expect(offered.seriesCandidates[0]).toMatchObject({ tmdbId: 4613, mediaType: 'tv', year: 2001 })

    const series = await identifyMovie(movie.id, 4613, 'tv')
    expect(series.mediaType).toBe('tv')
    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({ tmdbId: 4613, mediaType: 'tv' })
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
      toIdentify: true,
      keywordId: 9807,
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
    expect(url).toContain('toIdentify=true')
    // Batch Y5: Film Noir is a TMDB keyword.
    expect(url).toContain('keywordId=9807')
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

describe('Batch 37 memories calls', () => {
  it('calls both private endpoints and parses their distinct response shapes', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([
        {
          id: '5c9a1f7e-1f5e-4a7b-9a1e-0c2b3d4e5f60',
          movieId: movie.id,
          movieTitle: movie.title,
          posterPath: null,
          watchedAt: '2025-09-09',
          yearsAgo: 1,
          personalRating: 4.5,
        },
      ])))
      .mockResolvedValueOnce(new Response(JSON.stringify([
        {
          movieId: movie.id,
          movieTitle: movie.title,
          posterPath: null,
          lastWatchedAt: '2025-01-01',
          personalRating: 4.5,
        },
      ])))
    vi.stubGlobal('fetch', fetchMock)

    const [memories, suggestions] = await Promise.all([
      fetchOnThisDayMemories(),
      fetchRewatchSuggestions(),
    ])

    expect(memories[0].yearsAgo).toBe(1)
    expect(suggestions[0].lastWatchedAt).toBe('2025-01-01')
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      expect.stringContaining('/api/v1/memories/on-this-day'),
      expect.stringContaining('/api/v1/memories/rewatch-suggestions'),
    ])
  })
})


// ---------------------------------------------------------------------------
// Write surface (Batch 7)
// ---------------------------------------------------------------------------

const writtenItem = {
  id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
  movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302',
  movieTitle: 'Heat',
  formats: ['4k_uhd'],
  location: 'Front 2nd shelf',
  section: 'Front',
  shelf: '2nd',
  locationLabel: 'Front 2nd',
  subCategory: null,
  notes: null,
  condition: 'good',
  conditionUpdatedAt: '2026-09-08T14:00:00Z',
  hasPlaybackIssues: false,
  playbackNotes: null,
  purchasePrice: '19.99',
  purchaseSource: null,
  purchaseDate: null,
  listingStatus: 'in_collection',
  ebayListingUrl: null,
  listingPrice: null,
  updatedAt: '2026-09-08T15:00:00.123456Z',
  deletedAt: null,
}

const duplicate = {
  movieId: writtenItem.movieId,
  movieTitle: 'Heat',
  isDuplicate: true,
  existingCopies: [
    {
      id: '3f2504e0-4f89-11d3-9a0c-0305e82c3303',
      formats: ['blu_ray'],
      locationLabel: 'Back 6th',
      condition: 'good',
    },
  ],
  isUpgrade: true,
  bestFormatOwned: 'blu_ray',
}

const newCopy = { formats: ['4k_uhd'], hasPlaybackIssues: false }

describe('write surface', () => {
  it('adds a disc and parses the item back through the shared schema', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(writtenItem), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await addCollectionItem({
      ...newCopy,
      movieId: writtenItem.movieId,
      barcode: '5051892211475',
    })

    expect(result.locationLabel).toBe('Front 2nd')
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toMatchObject({
      movieId: writtenItem.movieId,
      barcode: '5051892211475',
    })
  })

  it('turns the 409 into a typed error carrying the §3.5 prompt', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: duplicate }), { status: 409 }),
      ),
    )

    // A plain Error would flatten the body to a string and lose the existing copies,
    // which are exactly what the prompt has to show.
    const error = await addCollectionItem({ ...newCopy, movieId: writtenItem.movieId }).catch(
      (caught: unknown) => caught,
    )

    expect(error).toBeInstanceOf(DuplicateItemError)
    expect((error as DuplicateItemError).duplicate.isUpgrade).toBe(true)
    expect((error as DuplicateItemError).duplicate.existingCopies[0].locationLabel).toBe(
      'Back 6th',
    )
  })

  it('asks the duplicate check about every format being added', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(duplicate)))
    vi.stubGlobal('fetch', fetchMock)

    const result = await checkDuplicate({ movieId: writtenItem.movieId }, ['4k_uhd', 'download'])

    expect(result.bestFormatOwned).toBe('blu_ray')
    expect(fetchMock.mock.calls[0][0]).toContain('format=4k_uhd&format=download')
  })

  it('sends the whole editable field set on an edit', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(writtenItem)))
    vi.stubGlobal('fetch', fetchMock)

    await updateCollectionItem(writtenItem.id, {
      formats: ['4k_uhd'],
      condition: 'damaged',
      hasPlaybackIssues: true,
      playbackNotes: 'Freezes an hour in',
    })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain(`/api/v1/collection/${writtenItem.id}`)
    expect(init.method).toBe('PUT')
    expect(JSON.parse(String(init.body))).toMatchObject({
      condition: 'damaged',
      hasPlaybackIssues: true,
    })
  })

  it('restores from the trash by table and id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(writtenItem)))
    vi.stubGlobal('fetch', fetchMock)

    await restoreCollectionItem(writtenItem.id)

    expect(fetchMock.mock.calls[0][0]).toContain(
      `/api/v1/trash/collection_items/${writtenItem.id}/restore`,
    )
  })

  it('asks the audit log for a whole film, not one disc', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, perPage: 50, pages: 0 })),
    )
    vi.stubGlobal('fetch', fetchMock)

    await fetchAudit({ movieId: writtenItem.movieId })

    expect(fetchMock.mock.calls[0][0]).toContain(`movieId=${writtenItem.movieId}`)
  })

  it('rejects a written item whose wire shape drifted', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ...writtenItem, locationLabel: undefined }), {
          status: 201,
        }),
      ),
    )

    await expect(
      addCollectionItem({ ...newCopy, movieId: writtenItem.movieId }),
    ).rejects.toBeInstanceOf(ZodError)
  })
})

describe('Batch 24 barcode calls', () => {
  const lookup = {
    barcode: '5051892211475',
    source: 'ebay',
    alreadyOwned: false,
    candidates: [
      {
        title: 'Blade Runner 2049',
        source: 'ebay',
        confidence: 0.7,
        movieId: null,
        tmdbId: 335984,
        year: 2017,
        posterPath: '/blade-runner.jpg',
        evidence: "eBay listings for this barcode read as 'blade runner 2049'",
      },
    ],
  }

  it('looks up without adding and parses every candidate through the shared schema', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(lookup)))
    vi.stubGlobal('fetch', fetchMock)

    const result = await lookupBarcode(lookup.barcode)

    expect(result.candidates[0]).toMatchObject({ title: 'Blade Runner 2049', tmdbId: 335984 })
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/v1/barcode/lookup')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ barcode: lookup.barcode })
  })

  it('records the separate confirmation action before a disc is added', async () => {
    const confirmed = {
      ...lookup,
      source: 'cache',
      candidates: [{ ...lookup.candidates[0], source: 'cache', confidence: 1 }],
    }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(confirmed)))
    vi.stubGlobal('fetch', fetchMock)

    await confirmBarcode({
      barcode: lookup.barcode,
      title: 'Blade Runner 2049',
      source: 'ebay',
      tmdbId: 335984,
    })

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain('/api/v1/barcode/confirm')
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toMatchObject({
      barcode: lookup.barcode,
      source: 'ebay',
      tmdbId: 335984,
    })
  })

  it('rejects a successful lookup whose confidence escaped its wire bounds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            ...lookup,
            candidates: [{ ...lookup.candidates[0], confidence: 1.2 }],
          }),
        ),
      ),
    )

    await expect(lookupBarcode(lookup.barcode)).rejects.toBeInstanceOf(ZodError)
  })
})
