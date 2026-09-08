import { describe, expect, it } from 'vitest'

import {
  candidateListSchema,
  collectionCopiesSchema,
  collectionFacetsSchema,
  healthResponseSchema,
  movieDetailSchema,
  moviePageSchema,
  profileResponseSchema,
  tokenPairSchema,
  watchLogPageSchema,
} from './schemas'

describe('healthResponseSchema', () => {
  it('parses the health response', () => {
    expect(healthResponseSchema.parse({ status: 'ok', commitSha: 'abc1234' })).toEqual({
      status: 'ok',
      commitSha: 'abc1234',
    })
  })

  it('rejects wire-shape drift', () => {
    expect(() => healthResponseSchema.parse({ status: 'healthy', commitSha: 'abc1234' })).toThrow()
    expect(() => healthResponseSchema.parse({ status: 'ok' })).toThrow()
  })
})

describe('tokenPairSchema', () => {
  it('parses a token pair', () => {
    const pair = {
      accessToken: 'a.b.c',
      refreshToken: 'd.e.f',
      tokenType: 'bearer' as const,
      expiresIn: 86400,
    }
    expect(tokenPairSchema.parse(pair)).toEqual(pair)
  })

  it('rejects wire-shape drift', () => {
    expect(() =>
      tokenPairSchema.parse({ accessToken: 'a', refreshToken: 'b', tokenType: 'Bearer', expiresIn: 1 }),
    ).toThrow()
    expect(() =>
      tokenPairSchema.parse({ accessToken: '', refreshToken: 'b', tokenType: 'bearer', expiresIn: 1 }),
    ).toThrow()
  })
})

describe('profileResponseSchema', () => {
  it('parses a profile', () => {
    const profile = {
      id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
      displayName: 'Craig',
      role: 'admin' as const,
      hasPin: true,
    }
    expect(profileResponseSchema.parse(profile)).toEqual(profile)
  })

  it('rejects an unknown role', () => {
    expect(() =>
      profileResponseSchema.parse({
        id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
        displayName: 'Craig',
        role: 'superadmin',
        hasPin: true,
      }),
    ).toThrow()
  })

  it('requires hasPin — a profile with no credential must be distinguishable', () => {
    expect(() =>
      profileResponseSchema.parse({
        id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
        displayName: 'Craig',
        role: 'admin',
      }),
    ).toThrow()
  })
})

const movieListItem = {
  id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
  title: '2001: A Space Odyssey',
  originalTitle: '2001: A Space Odyssey',
  year: 1968,
  posterPath: '/poster.jpg',
  backdropPath: '/backdrop.jpg',
  tmdbRating: 8.1,
  runtimeMinutes: 149,
  bestFormatOwned: '4k_uhd',
  bestHdrOwned: 'Dolby Vision',
  bestAudioOwned: 'Dolby Atmos',
  identified: true,
  copyCount: 2,
  locations: [{ section: 'Front', shelf: '2nd', label: 'Front 2nd' }],
  watched: false,
}

describe('Batch 5 collection schemas', () => {
  it('parses the paginated camel-case list without an envelope', () => {
    const page = {
      items: [movieListItem],
      totalMovies: 1843,
      totalItems: 1857,
      page: 1,
      perPage: 60,
      pages: 31,
    }
    expect(moviePageSchema.parse(page)).toEqual(page)
    expect(() => moviePageSchema.parse({ data: [movieListItem], meta: {} })).toThrow()
  })

  it('parses detail and copy locations', () => {
    const detail = {
      ...movieListItem,
      imdbId: 'tt0062622',
      overview: 'Humanity encounters a monolith.',
      tagline: null,
      genres: [{ id: 878, name: 'Science Fiction' }],
      cast: [{ personName: 'Keir Dullea', tmdbPersonId: 2453, characterName: 'Dave', profilePath: null }],
      crew: [{ personName: 'Stanley Kubrick', tmdbPersonId: 240, role: 'director' as const }],
      trailerKey: null,
      letterboxdSlug: null,
      mediaType: 'film',
    }
    expect(movieDetailSchema.parse(detail)).toEqual(detail)

    const copies = [{
      id: '08cb0e0b-4f14-470c-96d7-385d4b11ab03',
      formats: ['4k_uhd'],
      location: 'Front 2nd shelf',
      section: 'Front',
      shelf: '2nd',
      subCategory: null,
      notes: null,
      purchasePrice: null,
      purchaseSource: null,
      purchaseDate: null,
      condition: 'good',
      hasPlaybackIssues: false,
      playbackNotes: null,
      videoSpecs: null,
      audioSpecs: null,
      specialFeatures: null,
      regionCode: null,
      releaseLabel: null,
      listingStatus: 'in_collection',
    }]
    expect(collectionCopiesSchema.parse(copies)).toEqual(copies)
  })

  it('requires candidate context for an informed identification', () => {
    const candidates = {
      movieId: movieListItem.id,
      title: 'French Connection',
      query: 'French Connection',
      candidates: [{
        tmdbId: 1051,
        title: 'The French Connection',
        year: 1971,
        overview: 'A New York detective pursues a drug shipment.',
        posterPath: '/french-connection.jpg',
        confidence: 0.9,
        titleSimilarity: 0.9,
      }],
    }
    expect(candidateListSchema.parse(candidates)).toEqual(candidates)
    expect(() => candidateListSchema.parse({ ...candidates, candidates: [{ tmdbId: 1051 }] })).toThrow()
  })

  it('rejects snake_case drift', () => {
    expect(() => moviePageSchema.parse({
      items: [{ ...movieListItem, posterPath: undefined, poster_path: '/wrong.jpg' }],
      totalMovies: 1,
      totalItems: 1,
      page: 1,
      perPage: 60,
      pages: 1,
    })).toThrow()
  })
})

describe('Batch 6 location and watch-log schemas', () => {
  it('parses the facet vocabulary the filter bar is built from', () => {
    const facets = {
      sections: [
        {
          section: 'Front',
          movieCount: 550,
          itemCount: 550,
          shelves: [{ shelf: '2nd', movieCount: 119, itemCount: 119 }],
        },
        // A cabinet is a section with no shelves — the picker must be able to say so.
        { section: 'Top Big Cabinet', movieCount: 38, itemCount: 38, shelves: [] },
      ],
      unsectionedItemCount: 2,
      decades: [{ decade: 1940, movieCount: 203 }],
      undatedMovieCount: 757,
    }
    expect(collectionFacetsSchema.parse(facets)).toEqual(facets)
  })

  it('holds the API to the half-star scale', () => {
    const entry = {
      id: '5c9a1f7e-1f5e-4a7b-9a1e-0c2b3d4e5f60',
      movieId: movieListItem.id,
      movieTitle: '2001: A Space Odyssey',
      posterPath: '/poster.jpg',
      watchedAt: '2026-09-08',
      isRewatch: true,
      personalRating: 4.5,
      review: null,
    }
    const page = { items: [entry], total: 1, page: 1, perPage: 50, pages: 1 }
    expect(watchLogPageSchema.parse(page)).toEqual(page)

    // A rating outside §3.7's scale is wire drift, not a value to render.
    expect(() =>
      watchLogPageSchema.parse({ ...page, items: [{ ...entry, personalRating: 9 }] }),
    ).toThrow()
  })

  it('requires the location and watched fields the grid reads', () => {
    // Both shipped with their endpoint. A response missing them is a deploy-skew
    // signal, not something to paper over with a default.
    const { locations: _locations, ...withoutLocations } = movieListItem
    expect(() =>
      moviePageSchema.parse({
        items: [withoutLocations],
        totalMovies: 1,
        totalItems: 1,
        page: 1,
        perPage: 60,
        pages: 1,
      }),
    ).toThrow()
  })
})
