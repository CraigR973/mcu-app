import { describe, expect, it } from 'vitest'

import {
  auditEntrySchema,
  auditFieldChangeSchema,
  candidateListSchema,
  collectionCopiesSchema,
  collectionFacetsSchema,
  collectionItemSchema,
  duplicateCheckSchema,
  healthResponseSchema,
  movieDetailSchema,
  moviePageSchema,
  profileResponseSchema,
  tmdbSearchResponseSchema,
  tokenPairSchema,
  trashPageSchema,
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
      onboardingCompleted: false,
    }
    expect(profileResponseSchema.parse(profile)).toEqual(profile)
  })

  it('requires the onboarding flag rather than defaulting it', () => {
    // Defaulting it would mean an older API silently reads as "already onboarded",
    // which is the wizard never appearing for the person who needs it.
    expect(() =>
      profileResponseSchema.parse({
        id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
        displayName: 'Craig',
        role: 'admin',
        hasPin: true,
      }),
    ).toThrow()
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
      updatedAt: '2026-09-08T14:00:00Z',
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

// ---------------------------------------------------------------------------
// Write surface (Batch 7)
// ---------------------------------------------------------------------------

const collectionItem = {
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
  purchaseSource: 'Fopp',
  purchaseDate: '2026-09-01',
  listingStatus: 'in_collection',
  updatedAt: '2026-09-08T15:00:00.123456Z',
  deletedAt: null,
}

describe('collectionItemSchema', () => {
  it('parses a written item', () => {
    expect(collectionItemSchema.parse(collectionItem)).toEqual(collectionItem)
  })

  it('keeps the price a string so money never round-trips through a float', () => {
    expect(() =>
      collectionItemSchema.parse({ ...collectionItem, purchasePrice: 19.99 }),
    ).toThrow()
  })

  it('rejects wire-shape drift', () => {
    const { locationLabel: _dropped, ...missing } = collectionItem
    expect(() => collectionItemSchema.parse(missing)).toThrow()
  })
})

describe('duplicateCheckSchema', () => {
  it('parses the upgrade prompt the API decides on', () => {
    const parsed = duplicateCheckSchema.parse({
      movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302',
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
    })
    expect(parsed.isUpgrade).toBe(true)
    expect(parsed.existingCopies[0].locationLabel).toBe('Back 6th')
  })

  it('parses the "never heard of it" answer, where the film ids are null', () => {
    const parsed = duplicateCheckSchema.parse({
      movieId: null,
      movieTitle: null,
      isDuplicate: false,
      existingCopies: [],
      isUpgrade: false,
      bestFormatOwned: null,
    })
    expect(parsed.isDuplicate).toBe(false)
  })
})

describe('auditEntrySchema', () => {
  const entry = {
    id: '3f2504e0-4f89-11d3-9a0c-0305e82c3304',
    actorId: '3f2504e0-4f89-11d3-9a0c-0305e82c3305',
    actorName: 'Craig',
    actionType: 'update' as const,
    targetTable: 'collection_items',
    targetId: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
    changes: { condition: { from: 'good', to: 'damaged' } },
    createdAt: '2026-09-08T14:00:00Z',
  }

  it('parses a diff entry', () => {
    expect(auditEntrySchema.parse(entry).changes).toEqual({
      condition: { from: 'good', to: 'damaged' },
    })
  })

  it('parses an entry whose actor is gone — the row outlives the profile', () => {
    const orphan = auditEntrySchema.parse({ ...entry, actorId: null, actorName: null })
    expect(orphan.actorName).toBeNull()
    expect(orphan.targetId).toBe(entry.targetId)
  })

  it('rejects an action type outside the §3.20 vocabulary', () => {
    expect(() => auditEntrySchema.parse({ ...entry, actionType: 'tweaked' })).toThrow()
  })
})

describe('auditFieldChangeSchema', () => {
  it('narrows a diff value and passes over a snapshot scalar', () => {
    expect(auditFieldChangeSchema.safeParse({ from: null, to: 'damaged' }).success).toBe(true)
    expect(auditFieldChangeSchema.safeParse('another_copy').success).toBe(false)
  })
})

describe('trashPageSchema', () => {
  it('parses a page of removed discs', () => {
    const parsed = trashPageSchema.parse({
      items: [
        {
          id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
          targetTable: 'collection_items',
          movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302',
          movieTitle: 'Heat',
          posterPath: null,
          formats: ['dvd'],
          locationLabel: 'Unfiled',
          deletedAt: '2026-09-08T14:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      perPage: 200,
      pages: 1,
    })
    expect(parsed.items[0].locationLabel).toBe('Unfiled')
  })
})

describe('tmdbSearchResponseSchema', () => {
  it('flags a result the catalogue already has', () => {
    const parsed = tmdbSearchResponseSchema.parse({
      query: 'heat',
      results: [
        {
          tmdbId: 949,
          title: 'Heat',
          year: 1995,
          overview: 'A crew and the detective chasing it.',
          posterPath: '/heat.jpg',
          inCollection: true,
          movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302',
        },
      ],
    })
    expect(parsed.results[0].inCollection).toBe(true)
  })
})
