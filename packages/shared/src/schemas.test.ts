import { describe, expect, it } from 'vitest'

import {
  candidateListSchema,
  collectionCopiesSchema,
  healthResponseSchema,
  movieDetailSchema,
  moviePageSchema,
  profileResponseSchema,
  tokenPairSchema,
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
