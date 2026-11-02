import { describe, expect, it } from 'vitest'
import { cinemaProgrammeResponseSchema } from './schemas'

const id = '0a3282b1-50db-4af9-8d94-513dc8dd4bc3'
const showing = {
  id, venueId: id, sourceTitle: 'A film', startsAtUtc: '2026-11-02T20:00:00Z',
  endsAtUtc: null, screen: null, formats: [], releaseCategory: 'unclassified',
  categoryConfidence: 'unverified', categoryEvidence: { sourceUrl: null, description: 'Unverified run' },
  sourceReleaseDate: null, reissue: null,
  confirmation: 'unconfirmed', lastSeenUtc: '2026-11-02T08:00:00Z', observationStale: false,
  upstreamAge: 'unknown', bookingUrl: null,
}
const programme = {
  generatedAtUtc: '2026-11-02T08:00:00Z', window: { dateFrom: '2026-11-02', dateTo: '2026-11-02' },
  venues: [{
    id, slug: 'gft', name: 'Glasgow Film Theatre', source: 'gft',
    sourceUrl: 'https://www.glasgowfilm.org/all-listings/',
    officialUrl: 'https://www.glasgowfilm.org/all-listings/', collectionEnabled: false,
    coverage: [{ localDate: '2026-11-02', status: 'partial', observed: true, complete: false,
      lastAttemptUtc: '2026-11-02T08:00:00Z', lastSuccessUtc: '2026-11-02T08:00:00Z',
      sourceUpdateLabel: 'Monday 06:17', upstreamUtc: null, upstreamAge: 'unknown', error: null }],
  }],
  films: [{ id: 'source:1', title: 'A film', movieId: null, originalYear: null,
    yearConfidence: 'unverified', identityStatus: 'unverified', owned: null, watched: null,
    showings: [showing] }],
  categoryCounts: { newRelease: 0, olderFilm: 0, unclassified: 1 },
  matchedShowingCount: 1, returnedShowingCount: 1, truncated: false, selectionComplete: false,
}

describe('stored cinema programme', () => {
  it('retains explicit unknown identity, age, ownership and partial coverage', () => {
    expect(cinemaProgrammeResponseSchema.parse(programme)).toEqual(programme)
  })
  it.each(['newRelease', 'olderFilm', 'unclassified'])('accepts the %s run category', category => {
    const copy = structuredClone(programme)
    copy.films[0]!.showings[0]!.releaseCategory = category
    expect(cinemaProgrammeResponseSchema.safeParse(copy).success).toBe(true)
  })
  it.each(['olderOnly', '2026', 'recent'])('rejects guessed/retired category %s', category => {
    const copy = structuredClone(programme)
    copy.films[0]!.showings[0]!.releaseCategory = category
    expect(cinemaProgrammeResponseSchema.safeParse(copy).success).toBe(false)
  })
  it('rejects offset-free times and missing coverage certainty', () => {
    const copy = structuredClone(programme)
    copy.films[0]!.showings[0]!.startsAtUtc = '2026-11-02T20:00:00'
    expect(cinemaProgrammeResponseSchema.safeParse(copy).success).toBe(false)
    const missing = { ...programme, venues: [{ ...programme.venues[0], coverage: [{}] }] }
    expect(cinemaProgrammeResponseSchema.safeParse(missing).success).toBe(false)
  })
})
