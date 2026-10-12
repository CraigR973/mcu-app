import { describe, expect, it } from 'vitest'

import {
  activitySchema,
  dealSchema,
  ebayListingUrlSchema,
  ebayPriceEstimateSchema,
  ebayTargetsSchema,
  ebayPriceSegmentSchema,
  ebayAccountSchema,
  ebayConnectStartSchema,
  ebaySellingSchema,
  ebayWatchingSchema,
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
  beyondSearchResponseSchema,
  externalFilmSchema,
  movieListItemSchema,
  collectionFacetsSchema,
  bidTrialSchema,
  bidTrialStartSchema,
  highlightRatingSchema,
  highlightsSchema,
  rewatchedFilmSchema,
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
  filmReviewSchema,
  reviewScoreSchema,
  watchLogPageSchema,
  navSectionsSchema,
  watchHistoryStatusSchema,
  syncRunSchema,
  syncResponseSchema,
  collectionValueSchema,
  valuationStartSchema,
  specBackfillSchema,
  specDecisionSchema,
  specQueueSchema,
  identifyDecisionSchema,
  identifyOverviewSchema,
  identifyQueueSchema,
  identifySearchSchema,
  recentIdentificationsSchema,
  dealsRunSchema,
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
  // Batch T2: the API sends this on every list item now, null when unwatched.
  lastWatchedAt: null,
  // Batch U2: and this, empty when no copy records an edition.
  editions: [],
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
      // Batch V9: the API sends the film's reviews with its detail.
      reviews: [],
    }
    expect(movieDetailSchema.parse(detail)).toEqual(detail)

    const copies = [{
      id: '08cb0e0b-4f14-470c-96d7-385d4b11ab03',
      formats: ['4k_uhd'],
      location: 'Front 2nd shelf',
      section: 'Front',
      shelf: '2nd',
      subCategory: null,
      edition: 'SteelBook',
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
      ebayListingUrl: null,
      listingPrice: null,
      updatedAt: '2026-09-08T14:00:00Z',
      valuation: null,
    }]
    expect(collectionCopiesSchema.parse(copies)).toEqual(copies)
  })

  it('parses a film with editions, and a list or copy cached before editions existed — Batch U2', () => {
    const withEditions = { ...movieListItem, editions: ['Masters of Cinema', 'SteelBook'] }
    expect(movieListItemSchema.parse(withEditions).editions).toEqual(['Masters of Cinema', 'SteelBook'])

    const { editions: _none, ...cachedItem } = movieListItem
    expect(movieListItemSchema.parse(cachedItem).editions).toEqual([])
    expect(() => movieListItemSchema.parse({ ...movieListItem, editions: 'SteelBook' })).toThrow()

    const copy = collectionCopiesSchema.parse([{
      id: '08cb0e0b-4f14-470c-96d7-385d4b11ab03',
      formats: ['blu_ray'],
      location: null,
      section: null,
      shelf: null,
      subCategory: null,
      notes: null,
      purchasePrice: null,
      purchaseSource: null,
      purchaseDate: null,
      condition: null,
      hasPlaybackIssues: false,
      playbackNotes: null,
      videoSpecs: null,
      audioSpecs: null,
      specialFeatures: null,
      regionCode: null,
      releaseLabel: null,
      listingStatus: 'in_collection',
      ebayListingUrl: null,
      listingPrice: null,
      updatedAt: '2026-09-08T14:00:00Z',
    }])[0]
    expect(copy.edition).toBeNull()
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
      discsWithSpecs: 0,
      // Batch V4: the whole vocabulary rides along for the copy form's picker.
      allSections: ['Front', 'Back', 'Top Big Cabinet', "Craig's house"],
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
  edition: null,
  notes: null,
  condition: 'good',
  conditionUpdatedAt: '2026-09-08T14:00:00Z',
  hasPlaybackIssues: false,
  playbackNotes: null,
  purchasePrice: '19.99',
  purchaseSource: 'Fopp',
  purchaseDate: '2026-09-01',
  listingStatus: 'in_collection',
  ebayListingUrl: null,
  listingPrice: null,
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

describe('eBay price estimates (Batch 28)', () => {
  const segment = {
    formatCode: 'blu_ray',
    edition: 'standard',
    conditionId: '1000',
    conditionLabel: 'New',
    sampleSize: 29,
    median: '9.99',
    low: '4.16',
    high: '45.99',
    currency: 'GBP',
  }

  it('keeps money as a string', () => {
    // A price is money. A float median of 9.99 is not 9.99, and this one becomes a
    // suggested sale price in Batch 29.
    expect(() => ebayPriceSegmentSchema.parse({ ...segment, median: 9.99 })).toThrow()
    expect(ebayPriceSegmentSchema.parse(segment).median).toBe('9.99')
  })

  it('refuses a segment with no sample size', () => {
    // `DECISIONS.md` #129: a median without its sample size is the 149% overstatement
    // waiting to be believed. The field is required at the wire, not just in the UI.
    const { sampleSize: _dropped, ...withoutSampleSize } = segment
    expect(() => ebayPriceSegmentSchema.parse(withoutSampleSize)).toThrow()
  })

  it('accepts "unknown" as a condition id but not an empty one', () => {
    // A missing condition is its own bucket, never a default (#129).
    expect(ebayPriceSegmentSchema.parse({ ...segment, conditionId: 'unknown' })).toBeTruthy()
    expect(() => ebayPriceSegmentSchema.parse({ ...segment, conditionId: '' })).toThrow()
  })

  it('only knows two editions', () => {
    expect(() => ebayPriceSegmentSchema.parse({ ...segment, edition: 'steelbook' })).toThrow()
  })

  it('carries the rejections and the basis', () => {
    const parsed = ebayPriceEstimateSchema.parse({
      filmTitle: 'Blade Runner 2049',
      formatCode: 'blu_ray',
      marketplaceId: 'EBAY_GB',
      considered: 200,
      matched: 117,
      segments: [segment],
      headline: segment,
      rejected: { 'ships from JP, not GB': 7 },
      unusable: 0,
      basis: 'current asking prices',
    })

    expect(parsed.basis).toBe('current asking prices')
    expect(parsed.rejected['ships from JP, not GB']).toBe(7)
    expect(parsed.headline?.sampleSize).toBe(29)
  })

  it('allows a headline of null — nothing matched is an answer', () => {
    const parsed = ebayPriceEstimateSchema.parse({
      filmTitle: 'A Film Nobody Lists',
      formatCode: null,
      marketplaceId: 'EBAY_GB',
      considered: 200,
      matched: 0,
      segments: [],
      headline: null,
      rejected: {},
      unusable: 0,
      basis: 'current asking prices',
    })

    expect(parsed.headline).toBeNull()
  })

  it('parses the listing link and a null suggested price', () => {
    const parsed = ebayListingUrlSchema.parse({
      url: 'https://www.ebay.co.uk/sl/prelist/suggest?title=Jaws+%281975%29+Blu-ray',
      suggestedTitle: 'Jaws (1975) Blu-ray',
      suggestedPrice: null,
    })

    expect(parsed.url).toContain('title=')
    expect(parsed.suggestedPrice).toBeNull()
  })
})

describe('listing status (Batch 29)', () => {
  it('requires the listing fields rather than defaulting them', () => {
    // `.nullable()`, not `.nullable().default(null)`. A default would let a response that
    // simply stopped sending the fields parse cleanly as "not listed" — which is a wrong
    // answer wearing a correct shape, and exactly what `DECISIONS.md` #6's parse-every-
    // response rule exists to catch.
    const withoutThem = {
      id: '3f2504e0-4f89-11d3-9a0c-0305e82c3303',
      formats: ['blu_ray'],
      location: null,
      section: null,
      shelf: null,
      subCategory: null,
      notes: null,
      purchasePrice: null,
      purchaseSource: null,
      purchaseDate: null,
      condition: null,
      hasPlaybackIssues: false,
      playbackNotes: null,
      videoSpecs: null,
      audioSpecs: null,
      specialFeatures: null,
      regionCode: null,
      releaseLabel: null,
      listingStatus: 'sold',
      updatedAt: '2026-09-12T09:00:00Z',
    }
    expect(() => collectionCopiesSchema.parse([withoutThem])).toThrow()
    expect(
      collectionCopiesSchema.parse([
        { ...withoutThem, ebayListingUrl: null, listingPrice: '12.50' },
      ])[0].listingPrice,
    ).toBe('12.50')
  })

  it('keeps a sale price as a string', () => {
    // The same rule as every other money field here: a price must not round-trip through
    // a float on its way to being "what this disc fetched".
    const copy = {
      id: '3f2504e0-4f89-11d3-9a0c-0305e82c3303',
      formats: ['blu_ray'],
      location: null,
      section: null,
      shelf: null,
      subCategory: null,
      notes: null,
      purchasePrice: null,
      purchaseSource: null,
      purchaseDate: null,
      condition: null,
      hasPlaybackIssues: false,
      playbackNotes: null,
      videoSpecs: null,
      audioSpecs: null,
      specialFeatures: null,
      regionCode: null,
      releaseLabel: null,
      listingStatus: 'sold',
      ebayListingUrl: null,
      listingPrice: 12.5,
      updatedAt: '2026-09-12T09:00:00Z',
    }
    expect(() => collectionCopiesSchema.parse([copy])).toThrow()
  })
})

describe('navSectionsSchema', () => {
  it('parses the four counts', () => {
    const parsed = navSectionsSchema.parse({ boxSets: 0, collections: 3, deals: 0, loans: 12 })
    expect(parsed.collections).toBe(3)
    expect(parsed.boxSets).toBe(0)
  })

  it('refuses a negative count rather than hiding a destination on bad data', () => {
    // A negative would read as "empty" everywhere it is compared with `> 0`, which is the
    // quietest possible way for a destination to disappear.
    expect(navSectionsSchema.safeParse({ boxSets: -1, collections: 0, deals: 0, loans: 0 }).success).toBe(false)
  })

  it('refuses a missing section rather than defaulting it to zero', () => {
    // `undefined > 0` is false, so a dropped field would silently hide its destination.
    expect(navSectionsSchema.safeParse({ boxSets: 1, collections: 0, deals: 0 }).success).toBe(false)
  })
})

describe('watch history sync schemas', () => {
  const run = {
    id: 'abc',
    startedAt: '2026-09-15T10:00:00Z',
    finishedAt: '2026-09-15T10:00:04Z',
    trigger: 'manual',
    entries: 50,
    written: 3,
    alreadyImported: 45,
    ambiguous: 1,
    notInCollection: 1,
    error: null,
  }

  it('parses a status with no sync yet', () => {
    const parsed = watchHistoryStatusSchema.parse({
      letterboxdUsername: null,
      lastSync: null,
      watchCount: 0,
    })
    expect(parsed.lastSync).toBeNull()
  })

  it('keeps a failed run rather than dropping it', () => {
    // A sync that failed and left no trace is indistinguishable from one that never ran,
    // which is the expensive confusion given the 50-entry feed cap.
    const parsed = syncRunSchema.parse({ ...run, finishedAt: null, error: 'HTTPStatusError: 503' })
    expect(parsed.error).toContain('503')
  })

  it('carries the cadence warning separately from the counts', () => {
    const parsed = syncResponseSchema.parse({ run, ambiguities: ['Dunkirk (2017) → …'], feedWasFull: true })
    expect(parsed.feedWasFull).toBe(true)
    expect(parsed.ambiguities).toHaveLength(1)
  })

  it('refuses a run whose counts are negative', () => {
    expect(syncRunSchema.safeParse({ ...run, written: -1 }).success).toBe(false)
  })
})

describe('Batch T2 — one search', () => {
  it('reads a last watch date, and still parses an item cached before the field existed', () => {
    expect(movieListItemSchema.parse({ ...movieListItem, lastWatchedAt: '2025-03-12' }).lastWatchedAt).toBe('2025-03-12')
    const { lastWatchedAt: _dropped, ...cachedBeforeT2 } = movieListItem
    expect(movieListItemSchema.parse(cachedBeforeT2).lastWatchedAt).toBeNull()
  })

  it('accepts a film with no disc left, which the API has allowed since Batch 29', () => {
    expect(movieListItemSchema.parse({ ...movieListItem, copyCount: 0 }).copyCount).toBe(0)
    expect(() => movieListItemSchema.parse({ ...movieListItem, copyCount: -1 })).toThrow()
  })

  it('parses films beyond the shelf, with a flagged lookalike and an unchecked streaming line', () => {
    const response = {
      query: 'african queen',
      unavailable: false,
      items: [
        {
          tmdbId: 488, title: 'The African Queen', year: 1951, posterPath: '/aq.jpg', overview: '',
          movieId: null, lastWatchedAt: null, streamingOn: ['MUBI'], streamingChecked: true,
          maybeOwned: { movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3301', title: 'African Queen, The' },
        },
        {
          tmdbId: 489, title: 'Queen of Africa', year: null, posterPath: null, overview: '',
          movieId: null, lastWatchedAt: null, streamingOn: [], streamingChecked: false, maybeOwned: null,
        },
      ],
    }
    expect(beyondSearchResponseSchema.parse(response)).toEqual(response)
  })

  it('parses the film card', () => {
    const card = {
      tmdbId: 11050, title: 'The Card Player', year: 2004, posterPath: null, backdropPath: null,
      overview: 'A film nobody here owns.', runtimeMinutes: 103, genres: ['Thriller'],
      cast: ['Top Billed'], directors: ['Dario Argento'], movieId: null, owned: false,
      wanted: false, region: 'GB', link: null,
      offers: [{ providerId: 8, providerName: 'Netflix', logoPath: null, kind: 'flatrate' }],
    }
    expect(externalFilmSchema.parse(card)).toEqual(card)
  })
})

describe('Batch T6 — the collection\'s value', () => {
  const copy = {
    id: '3f2504e0-4f89-11d3-9a0c-0305e82c3303',
    formats: ['4k_uhd', 'blu_ray'],
    location: null,
    section: null,
    shelf: null,
    subCategory: null,
    notes: null,
    purchasePrice: null,
    purchaseSource: null,
    purchaseDate: null,
    condition: null,
    hasPlaybackIssues: false,
    playbackNotes: null,
    videoSpecs: null,
    audioSpecs: null,
    specialFeatures: null,
    regionCode: null,
    releaseLabel: null,
    listingStatus: 'in_collection',
    ebayListingUrl: null,
    listingPrice: null,
    updatedAt: '2026-09-12T09:00:00Z',
  }
  const valuation = {
    formatCode: '4k_uhd',
    status: 'priced',
    price: '24.99',
    currency: 'GBP',
    sampleSize: 7,
    conditionLabel: 'New',
    checkedAt: '2026-09-24T03:05:00Z',
    basis: 'current asking prices',
    minSample: 3,
    soldListingsUrl:
      'https://www.ebay.co.uk/sch/i.html?_nkw=Heat+4K&_sacat=617&LH_Sold=1&LH_Complete=1',
  }

  it('reads a copy cached before T6 as not valued yet (#205)', () => {
    expect(collectionCopiesSchema.parse([copy])[0].valuation).toBeNull()
  })

  it("reads a copy's stored price, and keeps it a string", () => {
    expect(collectionCopiesSchema.parse([{ ...copy, valuation }])[0].valuation).toEqual(valuation)
    expect(() =>
      collectionCopiesSchema.parse([{ ...copy, valuation: { ...valuation, price: 24.99 } }]),
    ).toThrow()
  })

  it('reads a stored price from an API before V8 as having no sold-listings link', () => {
    const { soldListingsUrl: _dropped, ...before } = valuation
    expect(collectionCopiesSchema.parse([{ ...copy, valuation: before }])[0].valuation).toEqual({
      ...before,
      soldListingsUrl: null,
    })
  })

  it('reads the total with a run in progress', () => {
    const value = {
      total: '12345.60',
      currency: 'GBP',
      basis: 'current asking prices',
      discs: 1457,
      pricedDiscs: 1302,
      notPricedDiscs: 103,
      uncheckedDiscs: 52,
      checkedFrom: '2026-09-23T03:00:00Z',
      checkedTo: '2026-09-24T03:10:00Z',
      due: 52,
      budgetLeft: 438,
      dailyShare: 750,
      minSample: 3,
      run: {
        id: '00000000-0000-4000-8000-000000000001',
        trigger: 'job',
        status: 'running',
        startedAt: '2026-09-24T03:00:00Z',
        finishedAt: null,
        budget: 750,
        calls: 312,
        priced: 280,
        notPriced: 30,
        failed: 2,
        remaining: null,
        lastError: null,
      },
    }
    expect(collectionValueSchema.parse(value)).toEqual(value)
    expect(collectionValueSchema.parse({ ...value, total: null, run: null }).total).toBeNull()
  })

  it('reads what the button did', () => {
    const started = { outcome: 'nothing_due', run: null, due: 0, budgetLeft: 750 }
    expect(valuationStartSchema.parse(started)).toEqual(started)
    expect(() => valuationStartSchema.parse({ ...started, outcome: 'queued' })).toThrow()
  })
})

describe('Batch T7 — the Blu-ray.com backfill', () => {
  it('reads facets cached before T7 as no disc having specs (#205)', () => {
    const facets = { sections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0 }
    expect(collectionFacetsSchema.parse(facets).discsWithSpecs).toBe(0)
    expect(collectionFacetsSchema.parse({ ...facets, discsWithSpecs: 12 }).discsWithSpecs).toBe(12)
  })

  it('reads facets cached before V4 as having no vocabulary, so the form falls back (#205)', () => {
    const facets = { sections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0 }
    expect(collectionFacetsSchema.parse(facets).allSections).toEqual([])
    expect(collectionFacetsSchema.parse({ ...facets, allSections: ["Craig's house"] }).allSections).toEqual([
      "Craig's house",
    ])
    expect(() => collectionFacetsSchema.parse({ ...facets, allSections: [''] })).toThrow()
  })

  it('reads a queued disc with its candidates', () => {
    const queue = {
      total: 1,
      items: [
        {
          lookupId: '00000000-0000-4000-8000-000000000011',
          collectionItemId: '00000000-0000-4000-8000-000000000012',
          movieId: '00000000-0000-4000-8000-000000000013',
          filmTitle: 'Fight Club',
          year: 1999,
          formatCode: 'blu_ray',
          location: null,
          status: 'needs_you',
          note: '3 UK editions match.',
          searchQuery: 'site:blu-ray.com Fight Club Blu-ray United Kingdom',
          candidates: [
            {
              url: 'https://www.blu-ray.com/movies/Fight-Club-Blu-ray/114797/',
              title: 'Fight Club Blu-ray (MetalPak) (United Kingdom)',
              country: 'United Kingdom',
              edition: 'MetalPak',
              matches: true,
              origin: 'search',
            },
          ],
        },
      ],
    }
    expect(specQueueSchema.parse(queue)).toEqual(queue)
  })

  it('reads the coverage with no batch yet', () => {
    const backfill = {
      searchConfigured: false,
      halted: false,
      haltedReason: null,
      coverage: { discs: 1250, withSpecs: 0, accepted: 0, needsYou: 0, noMatch: 0, skipped: 0, notSearched: 1250 },
      run: null,
      searchesThisMonth: 0,
      monthlyCeiling: 1500,
      searchesPerRun: 150,
      fetchesPerRun: 150,
    }
    expect(specBackfillSchema.parse(backfill)).toEqual(backfill)
  })

  it('refuses a decision it does not know', () => {
    const decision = { lookupId: '00000000-0000-4000-8000-000000000011', status: 'accepted', acceptedUrl: null, how: 'guessed' }
    expect(() => specDecisionSchema.parse(decision)).toThrow()
  })
})

describe('Batch T9 — identifying the unmatched films', () => {
  it('reads a waiting film with a choice that would merge into one already owned', () => {
    const queue = {
      total: 1,
      items: [
        {
          movieId: '00000000-0000-4000-8000-000000000021',
          title: 'Dunkirk',
          discs: [{ label: '4K · Front' }],
          watches: 0,
          note: 'TMDB holds another film of this title (1958).',
          proposedTmdbId: 374720,
          candidates: [
            {
              tmdbId: 374720,
              title: 'Dunkirk',
              year: 2017,
              posterPath: null,
              overview: '',
              votes: 18007,
              notes: ['18,007 TMDB votes'],
              inCollection: null,
            },
            {
              tmdbId: 36265,
              title: 'Dunkirk',
              year: 1958,
              posterPath: '/dunkirk.jpg',
              overview: 'The 1958 film.',
              votes: 77,
              notes: [],
              inCollection: {
                movieId: '00000000-0000-4000-8000-000000000022',
                title: 'Dunkirk',
                year: 1958,
                discs: 1,
                watches: 0,
              },
            },
          ],
        },
      ],
    }
    expect(identifyQueueSchema.parse(queue)).toEqual(queue)
  })

  it('reads the overview before any run', () => {
    const overview = {
      unidentified: 357,
      waiting: 357,
      setAsideTv: 0,
      setAsideNotFilm: 0,
      skipped: 0,
      identified: 0,
      run: null,
    }
    expect(identifyOverviewSchema.parse(overview)).toEqual(overview)
  })

  it('reads a search again and the recent list', () => {
    const search = { query: 'Peeping Tom', candidates: [] }
    expect(identifySearchSchema.parse(search)).toEqual(search)
    const recent = {
      items: [
        {
          actionId: '00000000-0000-4000-8000-000000000023',
          at: '2026-09-25T12:00:00+00:00',
          by: 'Craig',
          movieId: '00000000-0000-4000-8000-000000000024',
          replaced: 'Peepiing Tom',
          title: 'Peeping Tom',
          year: 1960,
          how: 'auto',
          merged: false,
          undone: false,
        },
      ],
    }
    expect(recentIdentificationsSchema.parse(recent)).toEqual(recent)
  })

  it('refuses an outcome it does not know', () => {
    const decision = { movieId: '00000000-0000-4000-8000-000000000025', outcome: 'guessed', title: 'X' }
    expect(() => identifyDecisionSchema.parse(decision)).toThrow()
  })
})

describe('Batch T8a — eBay price alerts', () => {
  const listing = {
    id: '00000000-0000-4000-8000-000000000061',
    kind: 'listing',
    status: 'met',
    title: 'THE BRAZEN BULL (NICTOPHOBIA) - Dvd  -',
    movieId: null,
    formatCode: null,
    targetPrice: '7.00',
    currency: 'GBP',
    url: 'https://www.ebay.co.uk/itm/168722516953',
    imageUrl: 'https://i.ebayimg.com/images/g/OywAAeSwqchqt4tc/s-l1600.jpg',
    isAuction: false,
    currentPrice: '6.99',
    currentPostage: '0.00',
    currentUrl: 'https://www.ebay.co.uk/itm/168722516953',
    endsAt: '2026-10-03T09:06:39Z',
    lastCheckedAt: '2026-09-26T10:00:00Z',
    metAt: '2026-09-26T10:00:00Z',
    lastError: null,
    createdAt: '2026-09-25T10:00:00Z',
  }

  it('reads the alerts and the latest pass, or none', () => {
    const run = {
      status: 'budget_spent',
      startedAt: '2026-09-26T10:20:00Z',
      finishedAt: '2026-09-26T10:21:00Z',
      targetsChecked: 2,
      dealsFound: 1,
    }
    expect(ebayTargetsSchema.parse({ items: [listing], lastRun: run })).toEqual({ items: [listing], lastRun: run })
    expect(ebayTargetsSchema.parse({ items: [], lastRun: null }).lastRun).toBeNull()
  })

  it('refuses a status or a format it does not know', () => {
    expect(() => ebayTargetsSchema.parse({ items: [{ ...listing, status: 'sold' }], lastRun: null })).toThrow()
    expect(() =>
      ebayTargetsSchema.parse({ items: [{ ...listing, kind: 'search', formatCode: 'vhs' }], lastRun: null }),
    ).toThrow()
  })
})

describe('Batch T8b — Connect eBay', () => {
  const listing = {
    itemId: '226100000010',
    title: 'Dog Soldiers 4K UHD Second Sight',
    url: 'https://www.ebay.co.uk/itm/226100000010',
    price: '24.99',
    currency: 'GBP',
    postage: '0.00',
    isAuction: false,
    bidCount: null,
    endsAt: '2026-10-10T20:00:00Z',
  }

  it('reads a connection, and one that is not set up, by name only', () => {
    const connected = {
      configured: true,
      missing: [],
      connected: true,
      accountName: 'mark_at_the_movies',
      connectedAt: '2026-10-04T09:00:00Z',
      note: null,
    }
    expect(ebayAccountSchema.parse(connected)).toEqual(connected)
    const unset = { ...connected, configured: false, missing: ['EBAY_RUNAME'], connected: false, accountName: null, connectedAt: null }
    expect(ebayAccountSchema.parse(unset).missing).toEqual(['EBAY_RUNAME'])
  })

  it("sends the browser only to eBay's own sign-in page", () => {
    const consent = 'https://auth.ebay.com/oauth2/authorize?client_id=x&response_type=code&state=s'
    expect(ebayConnectStartSchema.parse({ authorizeUrl: consent }).authorizeUrl).toBe(consent)
    expect(() => ebayConnectStartSchema.parse({ authorizeUrl: 'https://auth.ebay.com.evil.example/oauth2' })).toThrow()
    expect(() => ebayConnectStartSchema.parse({ authorizeUrl: 'http://auth.ebay.com/oauth2/authorize' })).toThrow()
  })

  it('reads the watch list with its saved searches, and the selling list with what sold', () => {
    const watching = {
      items: [listing, { ...listing, itemId: '226100000013', isAuction: true, bidCount: 3, postage: null }],
      savedSearches: [{ name: 'dog soldiers 4k', keywords: 'dog soldiers 4k', url: null }],
      totalItems: 2,
      fetchedAt: '2026-10-04T09:00:00Z',
    }
    expect(ebayWatchingSchema.parse(watching)).toEqual(watching)
    const selling = {
      active: [listing],
      sold: [
        {
          itemId: '226100000012',
          title: 'Alien DVD',
          url: 'https://www.ebay.co.uk/itm/226100000012',
          price: '3.50',
          currency: 'GBP',
          soldAt: '2026-09-28T09:12:44Z',
        },
      ],
      totalActive: 1,
      totalSold: 1,
      fetchedAt: '2026-10-04T09:00:00Z',
    }
    expect(ebaySellingSchema.parse(selling)).toEqual(selling)
  })

  it('refuses a listing without its link, or a negative count', () => {
    const watching = { items: [listing], savedSearches: [], totalItems: 1, fetchedAt: '2026-10-04T09:00:00Z' }
    expect(() => ebayWatchingSchema.parse({ ...watching, items: [{ ...listing, url: 'not a link' }] })).toThrow()
    expect(() => ebayWatchingSchema.parse({ ...watching, totalItems: -1 })).toThrow()
  })
})

describe('Batch 22b — checking the sale pages', () => {
  // Captured on 30 Sep from the real route, run in-process against production read-only,
  // over the Zavvi and Second Sight sale pages captured on 28-30 Sep. The other three
  // shops' lines are left out: their pages were not captured.
  const captured = {
    dryRun: true,
    written: 5,
    retailersWithDeals: 2,
    skippedOwned: 7,
    outcomes: [
      { retailer: 'Second Sight', ok: true, found: 16, kept: 1, skippedOwned: 0, rejected: 0, matched: 0, notDiscounted: 15, pageReasons: [], rejectedReasons: [], error: null },
      { retailer: 'Zavvi', ok: true, found: 12, kept: 4, skippedOwned: 7, rejected: 0, matched: 7, notDiscounted: 1, pageReasons: [], rejectedReasons: [], error: null },
    ],
  }

  it("reads a check's three numbers and each shop's counts", () => {
    const run = dealsRunSchema.parse(captured)
    expect(run).toEqual(captured)
    expect([run.written, run.retailersWithDeals, run.skippedOwned]).toEqual([5, 2, 7])
  })

  it('reads a check from an API a deploy behind as nothing undiscounted and no card reasons', () => {
    const older = {
      ...captured,
      outcomes: captured.outcomes.map(({ notDiscounted: _nd, rejectedReasons: _rr, ...rest }) => rest),
    }
    const run = dealsRunSchema.parse(older)
    expect(run.outcomes.map((outcome) => [outcome.notDiscounted, outcome.rejectedReasons])).toEqual([
      [0, []],
      [0, []],
    ])
  })

  it('refuses a negative count', () => {
    const outcome = { ...captured.outcomes[0], notDiscounted: -1 }
    expect(() => dealsRunSchema.parse({ ...captured, outcomes: [outcome] })).toThrow()
  })
})

describe('Batch V5 — Home\u2019s Highlights', () => {
  const film = { movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3401', title: 'Heat', year: 1995, posterPath: null }

  it('reads the three rows, each saying whose it is or what it rests on', () => {
    const highlights = {
      topRated: {
        items: [{ ...film, ratings: [{ personName: 'Craig', rating: 4.5 }] }],
        ratedBy: ['Craig'],
        notRatedBy: ['Mark'],
      },
      mostRewatched: [{ ...film, viewings: 3, byPerson: [{ personName: 'Craig', viewings: 2 }, { personName: 'Mark', viewings: 1 }] }],
      mostValuable: [
        {
          ...film,
          formatCode: '4k_uhd',
          price: '34.99',
          currency: 'GBP',
          basis: 'current asking prices',
          sampleSize: 7,
          checkedAt: '2026-09-26T03:00:00Z',
          copies: 1,
        },
      ],
      // Batch V9's fourth row, which the API now always sends.
      bestReviewed: [{ ...film, overall: 4, outOf: 5, formatCode: '4k_uhd' }],
    }
    expect(highlightsSchema.parse(highlights)).toEqual(highlights)
  })

  it('refuses a rating off the half-star scale and a "rewatch" seen once', () => {
    expect(() => highlightRatingSchema.parse({ personName: 'Craig', rating: 6 })).toThrow()
    expect(() => rewatchedFilmSchema.parse({ ...film, viewings: 1, byPerson: [] })).toThrow()
  })
})

describe('Batch V6 — the bid trial', () => {
  const total = (amount: string, discs: number) => ({ total: amount, discs })
  const summary = {
    formatCode: 'blu_ray',
    films: 1,
    withBids: 1,
    withBidsEndingSoon: 0,
    auctionsCounted: 3,
    endingSoon: 1,
    compared: 1,
    bidToAskingPercent: 60,
    cut: 1,
    auctionOnlyPlaces: 8,
    askingSample: 27,
    storedSample: 25,
    askingLost: 0,
    stored: total('23.00', 2),
    asking: total('19.98', 2),
    bids: total('12.00', 2),
    blend: { ...total('12.00', 2), fromBids: 2, fromAsking: 0 },
  }
  const trial = {
    id: '3f2504e0-4f89-41d3-9a0c-0305e82c3410',
    status: 'finished',
    startedAt: '2026-10-01T09:00:00Z',
    finishedAt: '2026-10-01T09:02:10Z',
    budget: 750,
    calls: 2,
    failed: 1,
    lastError: 'Heat (4k_uhd): eBay search failed (HTTP 500)',
    sampleSize: 100,
    minSample: 3,
    endingWindowHours: 24,
    dailyShare: 750,
    currency: 'GBP',
    report: {
      sampled: 2,
      films: [
        {
          movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3401',
          title: 'Blade Runner 2049',
          formatCode: 'blu_ray',
          copies: 2,
          stored: { price: '11.50', sampleSize: 25 },
          results: { total: 304, returned: 200, buyItNow: 192, auctionOnly: 8 },
          asking: { price: '9.99', sampleSize: 27 },
          bids: { counted: 3, withoutBids: 2, rejected: 4, price: '6.00', endingSoon: 1 },
          error: null,
        },
        {
          movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3402',
          title: 'Heat',
          formatCode: '4k_uhd',
          copies: 1,
          stored: { price: '20.00', sampleSize: 9 },
          results: null,
          asking: null,
          bids: null,
          error: 'eBay search failed (HTTP 500)',
        },
      ],
      formats: [summary],
      overall: { ...summary, formatCode: null },
    },
  }

  it('reads a trial and its report, with a film eBay did not answer for', () => {
    expect(bidTrialSchema.parse(trial)).toEqual(trial)
    const started = { outcome: 'started', trial: { ...trial, status: 'running', report: null }, sampled: 2, budgetLeft: 750 }
    expect(bidTrialStartSchema.parse(started)).toEqual(started)
  })

  it('reads a film written before it carried an error, and refuses an unknown outcome', () => {
    const { error: _error, ...older } = trial.report.films[0]
    const parsed = bidTrialSchema.parse({ ...trial, report: { ...trial.report, films: [older] } })
    expect(parsed.report?.films[0]?.error).toBeNull()
    expect(() => bidTrialStartSchema.parse({ outcome: 'nothing_due', trial: null, sampled: 0, budgetLeft: 0 })).toThrow()
  })
})

describe('Batch V8 — where an eBay find\'s "usually" comes from', () => {
  const find = {
    id: '00000000-0000-4000-8000-000000000081',
    retailer: 'eBay',
    title: 'Star Wars The Last Jedi 4K UHD + Blu-ray',
    url: 'https://www.ebay.co.uk/itm/298708357566',
    imageUrl: null,
    formatCode: '4k_uhd',
    price: '4.75',
    wasPrice: '18.00',
    currency: 'GBP',
    discountPercent: 74,
    movieId: '00000000-0000-4000-8000-000000000082',
    tmdbId: 181808,
    posterPath: null,
    genres: [],
    firstSeenAt: '2026-10-01T20:00:00Z',
    lastSeenAt: '2026-10-01T20:00:00Z',
    usualSources: [
      { source: 'eBay', price: '16.00' },
      { source: 'Zavvi', price: '20.00' },
    ],
    soldListingsUrl:
      'https://www.ebay.co.uk/sch/i.html?_nkw=Star+Wars%3A+The+Last+Jedi+4K&_sacat=617&LH_Sold=1&LH_Complete=1',
    condition: 'New',
    usualListings: 14,
  }

  it('reads the parts of the usual price and the sold-listings link', () => {
    expect(dealSchema.parse(find)).toEqual(find)
  })

  it('reads a deal from an API before V8 as having neither', () => {
    const { usualSources: _parts, soldListingsUrl: _sold, ...before } = find
    expect(dealSchema.parse(before)).toMatchObject({ usualSources: null, soldListingsUrl: null })
  })

  it('reads a deal from an API before X1 as having no condition or sample', () => {
    const { condition: _condition, usualListings: _listings, ...before } = find
    expect(dealSchema.parse(before)).toMatchObject({ condition: null, usualListings: null })
  })

  it('keeps each part a string, as money is everywhere', () => {
    expect(() =>
      dealSchema.parse({ ...find, usualSources: [{ source: 'eBay', price: 16 }] }),
    ).toThrow()
  })
})

describe('Batch V9 — a film\'s reviews', () => {
  const blurayCom = {
    site: 'bluray_com' as const,
    siteName: 'Blu-ray.com',
    url: 'https://www.blu-ray.com/movies/Dog-Soldiers-4K-Blu-ray/314666/',
    formatCode: '4k_uhd',
    title: 'Dog Soldiers 4K Blu-ray (4K Ultra HD + Blu-ray)',
    description: 'Dog Soldiers 4K Blu-ray Release Date August 23, 2022.',
    scores: [
      { heading: 'Movie', score: 3.5 },
      { heading: 'Overall', score: 4 },
    ],
    overall: 4,
    outOf: 5,
    scoresReadAt: '2026-10-03T02:20:00Z',
    note: null,
  }
  const avforums = {
    site: 'avforums' as const,
    siteName: 'AVForums',
    url: 'https://www.avforums.com/reviews/dog-soldiers-4k-blu-ray-review-dolby-vision.20024/',
    formatCode: '4k_uhd',
    title: 'Dog Soldiers 4K Blu-ray Review | AVForums',
    description: 'The 4K image, with Dolby Vision, is stunning.',
    scores: [],
    overall: null,
    outOf: null,
    scoresReadAt: null,
    note: 'AVForums does not allow apps to read its pages, so its scores are not shown.',
  }

  it('reads a scored Blu-ray.com review and an unscored AVForums link', () => {
    expect(filmReviewSchema.parse(blurayCom)).toEqual(blurayCom)
    expect(filmReviewSchema.parse(avforums)).toEqual(avforums)
  })

  it('refuses a site it does not know and a score out of range', () => {
    expect(() => filmReviewSchema.parse({ ...avforums, site: 'imdb' })).toThrow()
    expect(() => reviewScoreSchema.parse({ heading: 'Overall', score: 11 })).toThrow()
    expect(() => reviewScoreSchema.parse({ heading: 'Overall', score: 0 })).toThrow()
  })

  it('reads an API without reviews yet as none, on every shape that carries them', () => {
    const wanted = wantedItemSchema.parse({
      id: '3f2504e0-4f89-41d3-9a0c-0305e82c3401',
      movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3402',
      movieTitle: 'Dog Soldiers',
      year: 2002,
      posterPath: null,
      preferredFormat: '4k_uhd',
      preferredEdition: null,
      maxPrice: null,
      currency: 'GBP',
      isActive: true,
      notes: null,
      ownedAlready: false,
      addedAt: '2026-09-30T12:00:00Z',
    })
    expect(wanted.reviews).toEqual([])
    expect(
      highlightsSchema.parse({ topRated: { items: [], ratedBy: [], notRatedBy: [] }, mostRewatched: [], mostValuable: [] })
        .bestReviewed,
    ).toEqual([])
  })

  it('keeps a want\'s reviews in the order the API sends them', () => {
    const wanted = wantedItemSchema.parse({
      id: '3f2504e0-4f89-41d3-9a0c-0305e82c3401',
      movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3402',
      movieTitle: 'Dog Soldiers',
      year: 2002,
      posterPath: null,
      preferredFormat: '4k_uhd',
      preferredEdition: null,
      maxPrice: null,
      currency: 'GBP',
      isActive: true,
      notes: null,
      ownedAlready: false,
      addedAt: '2026-09-30T12:00:00Z',
      reviews: [blurayCom, avforums],
    })
    expect(wanted.reviews.map((review) => review.siteName)).toEqual(['Blu-ray.com', 'AVForums'])
  })
})
