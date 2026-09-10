import { describe, expect, it } from 'vitest'

import {
  activitySchema,
  auditEntrySchema,
  auditFieldChangeSchema,
  boxSetDetailSchema,
  boxSetSchema,
  builtInScraperListSchema,
  candidateListSchema,
  collectionCopiesSchema,
  aiAnswerSchema,
  aiStatusSchema,
  aiUsageSchema,
  collectionFacetsSchema,
  movieNightSessionSchema,
  movieNightVoteResultSchema,
  notificationPreferenceSchema,
  notificationSchema,
  pushSubscriptionSchema,
  vapidKeySchema,
  collectionItemSchema,
  completionFilmSchema,
  completionSetSchema,
  duplicateCheckSchema,
  giftFilmSchema,
  giftLinkSchema,
  giftPageSchema,
  healthResponseSchema,
  loanSchema,
  movieDetailSchema,
  moviePageSchema,
  onThisDayMemoriesSchema,
  ownershipStateSchema,
  profileResponseSchema,
  recommendationSchema,
  rewatchSuggestionsSchema,
  scraperTestSchema,
  smartCollectionFiltersSchema,
  smartCollectionResultsSchema,
  smartCollectionSchema,
  statsSchema,
  streamingSchema,
  tmdbSearchResponseSchema,
  tokenPairSchema,
  trashPageSchema,
  trashRowSchema,
  trashTableSchema,
  wantedItemSchema,
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

describe('memory schemas', () => {
  it('parse the private dashboard memories', () => {
    const memories = onThisDayMemoriesSchema.parse([
      {
        id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
        movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302',
        movieTitle: 'Heat',
        posterPath: null,
        watchedAt: '2025-09-09',
        yearsAgo: 1,
        personalRating: 4.5,
      },
    ])
    const suggestions = rewatchSuggestionsSchema.parse([
      {
        movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302',
        movieTitle: 'Heat',
        posterPath: null,
        lastWatchedAt: '2025-09-09',
        personalRating: 4.5,
      },
    ])

    expect(memories[0].yearsAgo).toBe(1)
    expect(suggestions[0].personalRating).toBe(4.5)
  })

  it('refuse a same-day watch and an unrated suggestion', () => {
    expect(onThisDayMemoriesSchema.safeParse([
        {
          id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
          movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302',
          movieTitle: 'Heat',
          posterPath: null,
          watchedAt: '2026-09-09',
          yearsAgo: 0,
          personalRating: null,
        },
      ]).success).toBe(false)
    expect(rewatchSuggestionsSchema.safeParse([
        {
          movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3302',
          movieTitle: 'Heat',
          posterPath: null,
          lastWatchedAt: '2025-09-09',
          personalRating: null,
        },
      ]).success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Batch 12 — box sets and smart collections
// ---------------------------------------------------------------------------

const UUID_A = '3f2504e0-4f89-11d3-9a0c-0305e82c3311'
const UUID_B = '3f2504e0-4f89-11d3-9a0c-0305e82c3312'

describe('boxSetSchema', () => {
  const base = {
    id: UUID_A,
    name: 'Columbia Noir Vol 4',
    label: 'Indicator',
    volumeNumber: 4,
    seriesId: null,
    seriesName: null,
    expectedCount: 4,
    posterUrl: null,
    notes: null,
    ownedCount: 3,
    isComplete: false,
    createdAt: '2026-09-09T00:00:00Z',
    updatedAt: '2026-09-09T00:00:00Z',
  }

  it('parses a partly-owned set', () => {
    const parsed = boxSetSchema.parse(base)
    expect(parsed.ownedCount).toBe(3)
    expect(parsed.isComplete).toBe(false)
  })

  it('keeps `isComplete` three-valued', () => {
    // A set whose size nobody recorded is unmeasured, not incomplete. Collapsing this
    // to a boolean in the schema would put a red mark against every unfilled set.
    const parsed = boxSetSchema.parse({ ...base, expectedCount: null, isComplete: null })
    expect(parsed.isComplete).toBeNull()
  })

  it('rejects an expected count of zero', () => {
    expect(boxSetSchema.safeParse({ ...base, expectedCount: 0 }).success).toBe(false)
  })
})

describe('boxSetDetailSchema', () => {
  it('carries members and sibling volumes', () => {
    const parsed = boxSetDetailSchema.parse({
      id: UUID_A,
      name: 'Columbia Noir',
      label: null,
      volumeNumber: null,
      seriesId: null,
      seriesName: null,
      expectedCount: null,
      posterUrl: null,
      notes: null,
      ownedCount: 0,
      isComplete: null,
      createdAt: '2026-09-09T00:00:00Z',
      updatedAt: '2026-09-09T00:00:00Z',
      items: [
        {
          collectionItemId: UUID_B,
          movieId: UUID_A,
          movieTitle: 'The Brothers Rico',
          posterPath: null,
          year: 1957,
          formats: ['blu_ray'],
          locationLabel: 'Top Small Cabinet',
          discNumber: 1,
        },
      ],
      volumes: [],
    })
    expect(parsed.items[0].discNumber).toBe(1)
    expect(parsed.volumes).toEqual([])
  })
})

describe('smartCollectionSchema', () => {
  const base = {
    id: UUID_A,
    name: 'Unwatched 4Ks from the 2010s',
    icon: 'sparkles',
    filters: {
      genreId: null,
      year: null,
      format: '4k_uhd',
      section: null,
      shelf: null,
      decadeFrom: 2010,
      decadeTo: 2010,
      minRating: null,
      watched: false,
    },
    sortBy: 'title',
    sortOrder: 'asc',
    isPinned: true,
    displayOrder: 0,
    createdAt: '2026-09-09T00:00:00Z',
    updatedAt: '2026-09-09T00:00:00Z',
  }

  it('parses the acceptance criterion’s own collection', () => {
    const parsed = smartCollectionSchema.parse(base)
    expect(parsed.filters.format).toBe('4k_uhd')
    expect(parsed.filters.watched).toBe(false)
  })

  it('refuses an icon outside the closed set', () => {
    // The value is rendered as a component name. An open vocabulary would mean either a
    // dynamic import of a server-supplied name or a silently blank icon.
    expect(smartCollectionSchema.safeParse({ ...base, icon: 'skull' }).success).toBe(false)
  })

  it('refuses a filter key the API cannot evaluate', () => {
    // Not `z.record(z.unknown())`: a key that parses here and is dropped server-side
    // would produce a collection listing the wrong films with total confidence.
    const parsed = smartCollectionFiltersSchema.safeParse({
      ...base.filters,
      orderBy: 'title; drop table movies',
    })
    // zod strips unknown keys rather than failing, so assert the key does not survive
    // into the parsed value — which is what stops it reaching a request body.
    expect(parsed.success).toBe(true)
    expect(parsed.success && 'orderBy' in parsed.data).toBe(false)
  })
})

describe('smartCollectionResultsSchema', () => {
  it('reuses the movie list item shape', () => {
    const parsed = smartCollectionResultsSchema.parse({
      collection: {
        id: UUID_A,
        name: 'Everything',
        icon: 'layers',
        filters: {
          genreId: null,
          year: null,
          format: null,
          section: null,
          shelf: null,
          decadeFrom: null,
          decadeTo: null,
          minRating: null,
          watched: null,
        },
        sortBy: 'title',
        sortOrder: 'asc',
        isPinned: false,
        displayOrder: 0,
        createdAt: '2026-09-09T00:00:00Z',
        updatedAt: '2026-09-09T00:00:00Z',
      },
      items: [
        {
          id: UUID_B,
          title: 'Heat',
          originalTitle: 'Heat',
          year: 1995,
          posterPath: null,
          backdropPath: null,
          tmdbRating: 8.3,
          runtimeMinutes: 170,
          bestFormatOwned: '4k_uhd',
          bestHdrOwned: null,
          bestAudioOwned: null,
          identified: true,
          copyCount: 1,
          locations: [],
          watched: false,
        },
      ],
      totalMovies: 1,
      totalItems: 1,
      page: 1,
      perPage: 60,
      pages: 1,
    })
    expect(parsed.items[0].title).toBe('Heat')
  })
})

describe('completionSetSchema', () => {
  const base = {
    id: UUID_A,
    setType: 'director',
    setKey: '2636',
    setName: 'Alfred Hitchcock',
    ownedCount: 12,
    totalCount: 61,
    missingCount: 49,
    percentComplete: 20,
    lastRefreshed: '2026-09-09T00:00:00Z',
  }

  it('parses the set §11.1’s acceptance criterion names', () => {
    const parsed = completionSetSchema.parse(base)
    expect(parsed.setName).toBe('Alfred Hitchcock')
    expect(parsed.totalCount).toBe(61)
  })

  it('refuses a percentage outside 0–100', () => {
    expect(completionSetSchema.safeParse({ ...base, percentComplete: 140 }).success).toBe(false)
  })

  it('accepts a set that has never been refreshed', () => {
    expect(completionSetSchema.safeParse({ ...base, lastRefreshed: null }).success).toBe(true)
  })
})

describe('completionFilmSchema', () => {
  it('ties `movieId` to a film that is actually owned', () => {
    // A missing film has no row in this database — that is what missing means — so its
    // poster comes from the set's cached member list.
    const missing = completionFilmSchema.parse({
      tmdbId: 539,
      title: 'Psycho',
      year: 1960,
      posterPath: '/psycho.jpg',
      owned: false,
      movieId: null,
    })
    expect(missing.movieId).toBeNull()
    expect(missing.posterPath).toBe('/psycho.jpg')
  })
})

describe('statsSchema', () => {
  const base = {
    totalMovies: 1857,
    totalItems: 1981,
    identifiedMovies: 1086,
    watchedMovies: 0,
    formats: [{ key: '4k_uhd', label: '4K UHD', itemCount: 346, movieCount: 340 }],
    genres: [],
    decades: [{ decade: 1940, label: '1940s', movieCount: 203 }],
    sections: [],
    mostWatched: [],
    spendOverTime: [],
    itemsWithPrice: 0,
  }

  it('accepts a dashboard whose watch and spend charts have no data', () => {
    // Both are empty in this collection today, and that must parse rather than throw —
    // the page's job is to say *why* they are empty, which it cannot do if the response
    // never arrives.
    const parsed = statsSchema.parse(base)
    expect(parsed.mostWatched).toEqual([])
    expect(parsed.itemsWithPrice).toBe(0)
  })

  it('keeps money in integer pence', () => {
    const parsed = statsSchema.parse({
      ...base,
      spendOverTime: [{ month: '2026-09', spentCents: 1299, cumulativeCents: 1299, itemCount: 1 }],
      itemsWithPrice: 1,
    })
    expect(parsed.spendOverTime[0].spentCents).toBe(1299)
  })
})

describe('activitySchema', () => {
  it('parses an event with no film behind it', () => {
    // An audit row can point at a table that has no poster — a box set, say.
    const parsed = activitySchema.parse({
      items: [
        {
          id: 'audit:1',
          kind: 'edited',
          at: '2026-09-09T00:00:00Z',
          actorName: 'Craig',
          movieId: null,
          movieTitle: null,
          posterPath: null,
          detail: 'box sets',
        },
      ],
      total: 1,
    })
    expect(parsed.items[0].movieId).toBeNull()
  })

  it('refuses an event kind the feed cannot render', () => {
    const bad = activitySchema.safeParse({
      items: [{ id: 'x', kind: 'exploded', at: '2026-09-09T00:00:00Z', actorName: null, movieId: null, movieTitle: null, posterPath: null, detail: null }],
      total: 1,
    })
    expect(bad.success).toBe(false)
  })
})

describe('loanSchema', () => {
  const base = {
    id: UUID_A,
    collectionItemId: UUID_B,
    movieId: UUID_A,
    movieTitle: 'Heat',
    posterPath: null,
    formats: ['blu_ray'],
    locationLabel: 'Front 2nd',
    borrowerName: 'A Friend',
    lentDate: '2026-09-01',
    dueDate: '2026-09-15',
    returnedDate: null,
    isOverdue: false,
    daysUntilDue: 6,
    notes: null,
  }

  it('parses an open loan', () => {
    expect(loanSchema.parse(base).isOverdue).toBe(false)
  })

  it('allows a negative countdown for an overdue loan', () => {
    // Negative is the whole point: "-10" is ten days late, and a nonnegative schema would
    // reject exactly the loans that matter.
    const parsed = loanSchema.parse({ ...base, isOverdue: true, daysUntilDue: -10 })
    expect(parsed.daysUntilDue).toBe(-10)
  })

  it('allows no due date at all', () => {
    const parsed = loanSchema.parse({ ...base, dueDate: null, daysUntilDue: null })
    expect(parsed.daysUntilDue).toBeNull()
  })
})

describe('trashRowSchema', () => {
  it('parses a deleted box set, which has no film behind it', () => {
    const parsed = trashRowSchema.parse({
      id: UUID_A,
      table: 'box_sets',
      label: 'Columbia Noir Vol 4',
      sublabel: 'Indicator',
      posterPath: null,
      movieId: null,
      deletedAt: '2026-09-09T00:00:00Z',
    })
    expect(parsed.movieId).toBeNull()
  })

  it('refuses a table the trash cannot serve', () => {
    // The example used to be `wanted_list`, which **Batch 18 built** — so it is a real tab
    // now. `smart_collections` hard-deletes by design (`DECISIONS.md` #55), so it is the
    // table that genuinely has no bin; accepting its name would let the UI ask for it and
    // render a confidently empty page.
    const bad = trashRowSchema.safeParse({
      id: UUID_A,
      table: 'smart_collections',
      label: 'x',
      sublabel: null,
      posterPath: null,
      movieId: null,
      deletedAt: '2026-09-09T00:00:00Z',
    })
    expect(bad.success).toBe(false)
  })
})

describe('streamingSchema', () => {
  const base = {
    movieId: UUID_A,
    region: 'GB',
    link: 'https://www.themoviedb.org/movie/949-heat/watch?locale=GB',
    offers: [
      { providerId: 337, providerName: 'Disney Plus', logoPath: '/d.jpg', kind: 'flatrate' },
    ],
    unidentified: false,
    unavailable: false,
  }

  it('parses a UK availability answer', () => {
    expect(streamingSchema.parse(base).offers[0].kind).toBe('flatrate')
  })

  it('keeps "could not look" separate from "nothing found"', () => {
    // 757 films in this collection had no TMDB id. Rendering both as an empty list would
    // tell someone a film streams nowhere when nobody ever asked.
    const parsed = streamingSchema.parse({
      ...base,
      link: null,
      offers: [],
      unidentified: true,
    })
    expect(parsed.unidentified).toBe(true)
  })

  it('refuses a region that is not two letters', () => {
    // TMDB answers an unrecognised key with an empty map rather than an error, so a bad
    // region makes every film look unavailable and nothing says why.
    expect(streamingSchema.safeParse({ ...base, region: 'GBR' }).success).toBe(false)
  })
})

describe('recommendationSchema', () => {
  it('has all three of §7.2’s ownership states since Batch 18', () => {
    // Batch 16 shipped two and this test asserted the third was *refused*, because §3.5's
    // `wanted_list` did not exist and a badge that could never appear is a legend entry
    // pointing at nothing. Batch 18 built the table, so the assertion inverts.
    const wanted = recommendationSchema.safeParse({
      tmdbId: 1,
      title: 'A Film',
      year: 2026,
      overview: '',
      posterPath: null,
      ownership: 'wanted',
      movieId: null,
    })
    expect(wanted.success).toBe(true)
  })

  it('still refuses a state the app cannot produce', () => {
    const bad = recommendationSchema.safeParse({
      tmdbId: 1,
      title: 'A Film',
      year: 2026,
      overview: '',
      posterPath: null,
      ownership: 'preordered',
      movieId: null,
    })
    expect(bad.success).toBe(false)
  })
})

describe('wantedItemSchema', () => {
  const base = {
    id: UUID_A,
    movieId: UUID_B,
    movieTitle: 'A Film To Buy',
    year: 2026,
    posterPath: null,
    preferredFormat: '4k_uhd',
    preferredEdition: null,
    maxPrice: '19.99',
    currency: 'GBP',
    isActive: true,
    notes: null,
    ownedAlready: false,
    addedAt: '2026-09-09T00:00:00Z',
  }

  it('keeps a price as a decimal string', () => {
    // Money never round-trips through a float — this is the threshold Batch 20's alerts
    // compare against, and a float compares wrongly at exactly the boundary.
    expect(wantedItemSchema.parse(base).maxPrice).toBe('19.99')
  })

  it('allows wanting a film that is already owned', () => {
    // A DVD-to-4K upgrade is exactly that, so it is flagged rather than refused.
    expect(wantedItemSchema.parse({ ...base, ownedAlready: true }).ownedAlready).toBe(true)
  })

  it('separates "no longer looking" from removal', () => {
    // `isActive` is a decision; deletion is an accident. Only the second goes to Trash.
    expect(wantedItemSchema.parse({ ...base, isActive: false }).isActive).toBe(false)
  })
})

describe('ownershipStateSchema', () => {
  it('has all three of §7.2’s states now that Batch 18 built the table', () => {
    // Batch 16 shipped two, because a `wanted` badge that could never appear would be a
    // legend entry pointing at nothing.
    expect(ownershipStateSchema.safeParse('wanted').success).toBe(true)
    expect(ownershipStateSchema.safeParse('owned').success).toBe(true)
    expect(ownershipStateSchema.safeParse('unowned').success).toBe(true)
    expect(ownershipStateSchema.safeParse('borrowed').success).toBe(false)
  })
})

describe('trashTableSchema', () => {
  it('accepts the two tables Batch 15 refused and Batch 18 built', () => {
    expect(trashTableSchema.safeParse('wanted_list').success).toBe(true)
    expect(trashTableSchema.safeParse('retailers').success).toBe(true)
  })

  it('still refuses a table with no bin', () => {
    // `smart_collections` hard-deletes by design — there is nothing for a trash to hold.
    expect(trashTableSchema.safeParse('smart_collections').success).toBe(false)
  })
})

describe('scraperTestSchema', () => {
  const base = {
    fetched: true,
    finalUrl: 'https://store.example/search?q=Heat',
    title: 'Heat [4K UHD]',
    rawPriceText: '£19.99',
    price: '19.99',
    currency: 'GBP',
    listingUrl: 'https://store.example/p/heat',
    ok: true,
    reasons: [],
    error: null,
  }

  it('parses a good test result', () => {
    expect(scraperTestSchema.parse(base).ok).toBe(true)
  })

  it('models "fetched fine, but this is not a price" as its own outcome', () => {
    // The failure this whole batch is built around: the request works, the number parses,
    // and it is wrong. `ok: false` with `fetched: true` is the shape that says so.
    const parsed = scraperTestSchema.parse({
      ...base,
      ok: false,
      price: '5.00',
      rawPriceText: 'Save £5.00',
      reasons: ['page title has nothing in common with "North by Northwest"'],
    })
    expect(parsed.fetched).toBe(true)
    expect(parsed.ok).toBe(false)
    expect(parsed.reasons).toHaveLength(1)
  })

  it('keeps a price as a string', () => {
    // Money never round-trips through a float, all the way out to the screen.
    expect(typeof scraperTestSchema.parse(base).price).toBe('string')
  })
})

describe('builtInScraperListSchema', () => {
  it('carries the unverified list — the sources that cannot be scraped from here', () => {
    // A selector nobody has run against a live page is a guess, and the schema makes the
    // app say so. HMV, CEX, Amazon and Blu-ray.com stay unverified permanently.
    const parsed = builtInScraperListSchema.parse({
      items: [
        {
          name: 'HMV',
          searchUrlTemplate: 'https://store.hmv.com/search?q={query}',
          scraperConfig: { price: '.price' },
          verified: false,
          note: null,
        },
      ],
      unverified: ['HMV'],
    })
    expect(parsed.items[0].verified).toBe(false)
    expect(parsed.unverified).toEqual(['HMV'])
  })
})

describe('giftPageSchema', () => {
  it('parses the public page', () => {
    const parsed = giftPageSchema.parse({
      title: "Mark's Christmas 2026",
      films: [
        {
          title: 'Heat',
          year: 1995,
          posterPath: '/heat.jpg',
          preferredFormat: '4k_uhd',
          maxPrice: '24.99',
          currency: 'GBP',
          retailerLinks: [{ name: 'HMV', url: 'https://store.hmv.com/search?q=Heat' }],
        },
      ],
      total: 1,
      filterConfig: { maxPrice: '30.00', formats: ['4k_uhd'] },
    })
    expect(parsed.films[0].retailerLinks[0].name).toBe('HMV')
  })

  it('has no field that could say what the recipient already owns', () => {
    // The public schema is deliberately unrelated to any admin type. If it extended one,
    // a field added there would appear here — and whether someone owns a film is not what
    // a family member needs in order to buy a present.
    const film = giftFilmSchema.parse({
      title: 'Heat',
      year: 1995,
      posterPath: null,
      preferredFormat: null,
      maxPrice: null,
      currency: 'GBP',
      retailerLinks: [],
    })
    expect(Object.keys(film).sort()).toEqual([
      'currency',
      'maxPrice',
      'posterPath',
      'preferredFormat',
      'retailerLinks',
      'title',
      'year',
    ])
  })
})

describe('giftLinkSchema', () => {
  it('refuses a slug short enough to enumerate', () => {
    // §6.26's worked example is `/gift/a8f3b2c1` — eight hex characters, 32 bits. What
    // would be enumerated is a named person's wish list.
    const short = giftLinkSchema.safeParse({
      id: UUID_A,
      slug: 'a8f3b2c1',
      path: '/gift/a8f3b2c1',
      title: 'x',
      filterConfig: { maxPrice: null, formats: [] },
      expiresAt: null,
      viewCount: 0,
      lastViewedAt: null,
      isActive: true,
      isUsable: true,
      createdAt: '2026-09-09T00:00:00Z',
    })
    expect(short.success).toBe(false)
  })
})

describe('notification schemas', () => {
  const subscription = {
    id: UUID_A,
    deviceLabel: "Craig's phone",
    endpointPreview: '…f3b2c1a8f3b2',
    pushService: 'fcm.googleapis.com',
    userAgent: 'Mozilla/5.0',
    createdAt: '2026-09-09T00:00:00Z',
    lastUsedAt: null,
    failureCount: 0,
  }

  it('accepts a device record', () => {
    expect(pushSubscriptionSchema.parse(subscription).pushService).toBe('fcm.googleapis.com')
  })

  it('drops an endpoint if the API ever starts sending one', () => {
    // The endpoint is a bearer capability: anyone holding it can push to that device. The
    // schema is the last place that can stop it reaching a browser's memory, so this is a
    // guard against a future change to the response rather than against today's.
    const parsed = pushSubscriptionSchema.parse({
      ...subscription,
      endpoint: 'https://fcm.googleapis.com/fcm/send/secret',
    })
    expect(parsed).not.toHaveProperty('endpoint')
  })

  it('treats "push is not configured" as a value, not an error', () => {
    // The TMDB shape: a feature absent from the deployment. The UI can only say so if the
    // schema lets the API say so.
    expect(vapidKeySchema.parse({ publicKey: null, configured: false }).configured).toBe(false)
  })

  it('refuses a notification status outside the vocabulary', () => {
    const parsed = notificationSchema.safeParse({
      id: UUID_A,
      category: 'deals',
      status: 'delivered-probably',
      title: 'x',
      body: 'y',
      url: null,
      createdAt: '2026-09-09T00:00:00Z',
      deliverAfter: null,
      deferredReason: null,
      suppressedReason: null,
      sentAt: null,
      deliveredCount: 0,
    })
    expect(parsed.success).toBe(false)
  })

  it('refuses a digest hour outside a day', () => {
    const parsed = notificationPreferenceSchema.safeParse({
      dealsEnabled: true,
      saleEventsEnabled: true,
      releasesEnabled: true,
      loansEnabled: true,
      movieNightEnabled: true,
      digestMode: true,
      digestHourLocal: 25,
      quietHoursStart: null,
      quietHoursEnd: null,
      quietHoursTimezone: 'Europe/London',
    })
    expect(parsed.success).toBe(false)
  })
})

describe('AI assistant schemas', () => {
  it('keeps cost as a string, not a number', () => {
    // A short question costs a fraction of a penny. Parsing it as a float and rendering
    // it back would not be what was billed, and the daily cost cap counts these.
    const answer = aiAnswerSchema.parse({
      id: UUID_A,
      text: 'Heat is on the Front 2nd shelf.',
      model: 'claude-sonnet-5',
      inputTokens: 1200,
      outputTokens: 45,
      cacheReadTokens: 0,
      cacheWriteTokens: 0,
      costUsd: '0.002850',
      stopReason: 'end_turn',
      latencyMs: 900,
      error: null,
    })
    expect(answer.costUsd).toBe('0.002850')
    expect(typeof answer.costUsd).toBe('string')
  })

  it('treats "the assistant is not configured" as a value, not an error', () => {
    // The TMDB shape, again: a feature absent from the deployment that the UI can name.
    expect(aiStatusSchema.parse({ configured: false, model: 'claude-sonnet-5' }).configured).toBe(
      false,
    )
  })

  it('carries the limit message only alongside the blocked flag', () => {
    const usage = aiUsageSchema.parse({
      messages: 50,
      messageCap: 50,
      messagesRemaining: 0,
      costUsd: '0.140000',
      costCapUsd: '2.00',
      blocked: true,
      limitMessage: "You have used all 50 of today's messages.",
      resetsAt: '2026-09-11T23:00:00Z',
    })
    expect(usage.blocked).toBe(true)
    expect(usage.limitMessage).toContain('50')
  })
})

describe('movie night schemas', () => {
  const session = {
    id: UUID_A,
    status: 'open' as const,
    filters: { decadeFrom: 2000 },
    inviteToken: 'a'.repeat(22),
    invitePath: `/movie-night/join/${'a'.repeat(22)}`,
    participantCount: 2,
    createdAt: '2026-09-10T20:00:00Z',
    endedAt: null,
  }

  it('refuses an invite token short enough to enumerate', () => {
    // The same floor Batch 27 settled on after §6.26's 32-bit example: the URL is the
    // whole credential for joining, so guessing must not be a strategy.
    expect(movieNightSessionSchema.safeParse({ ...session, inviteToken: 'a8f3b2c1' }).success).toBe(
      false,
    )
  })

  it('accepts a live session', () => {
    expect(movieNightSessionSchema.parse(session).participantCount).toBe(2)
  })

  it('refuses a session with nobody in it', () => {
    // The creator is always a participant, so zero means something went wrong upstream.
    expect(movieNightSessionSchema.safeParse({ ...session, participantCount: 0 }).success).toBe(
      false,
    )
  })

  it('treats "no match" as a value rather than an absent field', () => {
    // `match` is non-null only on the swipe that completes one; a missing key would make
    // "not yet" and "malformed response" the same thing.
    expect(movieNightVoteResultSchema.parse({ recorded: true, match: null }).match).toBeNull()
  })
})
