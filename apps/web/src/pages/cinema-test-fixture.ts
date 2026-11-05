import type { CinemaProgrammeResponse } from '@mcu/shared'
export const CINEMA_NOW = Date.parse('2026-11-03T17:00:00Z')
const uid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
export function cinemaFixture(): CinemaProgrammeResponse {
  const venues = [1, 2].map((n) => ({
    id: uid(n), slug: `venue-${n}`, name: n === 1 ? 'Vue Glasgow St Enoch' : 'ODEON Kilmarnock', source: n === 1 ? 'vue' : 'cinematimes',
    sourceUrl: n === 1 ? 'https://www.myvue.com/cinema/glasgow-st-enoch/whats-on' : 'https://cinematimes.com/uk/glasgow/cinemas/odeon-kilmarnock/',
    officialUrl: n === 1 ? 'https://www.myvue.com/cinema/glasgow-st-enoch/whats-on' : 'https://www.odeon.co.uk/cinemas/kilmarnock/', collectionEnabled: true,
    coverage: [{ localDate: '2026-11-03', status: 'partial' as const, observed: true, complete: false, lastAttemptUtc: '2026-11-03T16:00:00Z', lastSuccessUtc: '2026-11-03T16:00:00Z', sourceUpdateLabel: null, upstreamUtc: null, upstreamAge: 'unknown' as const, error: null }],
  }))
  const showing = (n: number, releaseCategory: 'newRelease' | 'olderFilm' | 'unclassified', venue = 1) => ({
    id: uid(10 + n), venueId: uid(venue), sourceTitle: 'A returning favourite', startsAtUtc: `2026-11-03T${19 + n}:00:00Z`, endsAtUtc: null, screen: null, formats: ['IMAX'], releaseCategory,
    sourceReleaseDate: null, reissue: releaseCategory === 'olderFilm' ? true : null, categoryConfidence: releaseCategory === 'unclassified' ? 'unverified' as const : 'verified' as const,
    categoryEvidence: { sourceUrl: null, description: releaseCategory === 'olderFilm' ? 'Anniversary programme, corroborated earlier release' : 'Release run unverified' }, categoryReason: null as string | null, confirmation: 'confirmed' as const,
    lastSeenUtc: '2026-11-03T16:00:00Z', observationStale: false, upstreamAge: 'unknown' as const, bookingUrl: venue === 1 ? 'https://www.myvue.com/book-tickets/summary/10097/123' : 'https://www.odeon.co.uk/ticketing/seat-picker/?showtimeId=615-123',
  })
  const base = { movieId: null, originalYear: null, yearConfidence: 'unverified' as const, identityStatus: 'unverified' as const, owned: null, watched: null }
  return { generatedAtUtc: '2026-11-03T16:30:00Z', window: { dateFrom: '2026-11-03', dateTo: '2026-11-03' }, venues,
    films: [
      { ...base, id: 'tmdb:1417', title: 'A returning favourite', originalYear: 1990, yearConfidence: 'verified', identityStatus: 'verified', owned: true, watched: true, showings: [showing(1, 'olderFilm'), showing(2, 'olderFilm', 2)] },
      { ...base, id: 'source:new', identityStatus: 'verified', title: 'A current first run', showings: [showing(3, 'newRelease')] },
      { ...base, id: 'source:unknown', title: 'An uncertain programme', showings: [showing(4, 'unclassified')] },
    ], categoryCounts: { newRelease: 1, olderFilm: 2, unclassified: 1 }, matchedShowingCount: 4, returnedShowingCount: 4, truncated: false, selectionComplete: false,
  }
}
