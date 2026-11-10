import type { CinemaFilmDetail, CinemaFilms } from '@mcu/shared'
import { CINEMA_NOW } from './cinema-test-fixture'

export { CINEMA_NOW }
const uid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
export const VUE = uid(1)
export const ODEON = uid(2)
const dates = Array.from({ length: 14 }, (_, i) => new Date(Date.UTC(2026, 10, 3 + i)).toISOString().slice(0, 10))

/** Vue lists two days and ODEON seven, as on 4 Nov; the checks are partial, as they are live. */
function venues(): CinemaFilms['venues'] {
  return [
    { n: 1, slug: 'vue-st-enoch', name: 'Vue Glasgow St Enoch', source: 'vue', url: 'https://www.myvue.com/cinema/glasgow-st-enoch/whats-on', listed: 2 },
    { n: 2, slug: 'odeon-kilmarnock', name: 'ODEON Kilmarnock', source: 'cinematimes', url: 'https://www.odeon.co.uk/cinemas/kilmarnock/', listed: 7 },
  ].map(({ n, slug, name, source, url, listed }) => ({
    id: uid(n), slug, name, source, sourceUrl: url, officialUrl: url, collectionEnabled: true,
    coverage: dates.map((localDate, i) => ({
      localDate, status: 'partial' as const, observed: i < listed, complete: false,
      lastAttemptUtc: '2026-11-03T16:00:00Z', lastSuccessUtc: '2026-11-03T16:00:00Z', sourceUpdateLabel: null,
      upstreamUtc: null, upstreamAge: 'unknown' as const, error: null,
    })),
  }))
}

type Card = CinemaFilms['films'][number]
const base = {
  sourceTitles: [] as string[], posterPath: null, tmdbId: null, movieId: null, originalYear: null, yearConfidence: 'unverified' as const,
  directors: [] as string[], runtimeMinutes: null, identityStatus: 'verified' as const, identityReason: null, owned: null, watched: null,
}
/** AE5: each time with its ticket link, as the API sends them since; the ODEON's in IMAX. */
const booking = (venueId: string, n: number) => venueId === ODEON
  ? `https://www.odeon.co.uk/ticketing/seat-picker/?showtimeId=019-${String(n)}`
  : `https://www.myvue.com/book-tickets/summary/10097/${String(n)}`
const slot = (venueId: string, localDate: string, releaseCategory: Card['slots'][number]['releaseCategory'], runReason: string | null, ...startsAtUtc: string[]) =>
  ({
    venueId, localDate, releaseCategory, runReason, startsAtUtc,
    times: startsAtUtc.map((at, n) => ({ at, bookingUrl: booking(venueId, n + 1), formats: venueId === ODEON ? ['imax'] : [] })),
  })

export function filmsFixture(): CinemaFilms {
  const films: Card[] = [
    {
      ...base, key: 'tmdb-1417', kind: 'film', title: 'A returning favourite', sourceTitles: ['A returning favourite'], posterPath: '/fav.jpg',
      tmdbId: 1417, movieId: uid(90), originalYear: 1990, yearConfidence: 'verified', owned: true, watched: true,
      slots: [slot(VUE, '2026-11-03', 'olderFilm', 'UK release 1990 · rerun', '2026-11-03T20:00:00Z'), slot(ODEON, '2026-11-03', 'olderFilm', 'UK release 1990 · rerun', '2026-11-03T21:00:00Z')],
    },
    {
      ...base, key: 'tmdb-2001', kind: 'film', title: 'A current first run', posterPath: '/new.jpg', tmdbId: 2001, originalYear: 2026, yearConfidence: 'verified',
      slots: [slot(ODEON, '2026-11-05', 'newRelease', 'UK release 23 Oct 2026 · first run', '2026-11-05T19:30:00Z')],
    },
    {
      ...base, key: 'tmdb-2002', kind: 'film', title: 'Opening later', posterPath: '/later.jpg', tmdbId: 2002,
      slots: [slot(ODEON, '2026-11-12', 'newRelease', 'UK release 12 Nov 2026 · first run', '2026-11-12T19:00:00Z')],
    },
    {
      ...base, key: `listing-${uid(50)}`, kind: 'listing', title: 'An uncertain programme', identityStatus: 'unverified', identityReason: 'not yet looked up on TMDB',
      slots: [slot(VUE, '2026-11-03', 'unclassified', null, '2026-11-03T22:00:00Z')],
    },
    {
      ...base, key: `listing-${uid(51)}`, kind: 'listing', title: 'Waiting film', identityStatus: 'review', identityReason: 'the title matches, but nothing else agrees',
      slots: [slot(ODEON, '2026-11-04', 'unclassified', null, '2026-11-04T18:00:00Z')],
    },
    {
      ...base, key: `listing-${uid(52)}`, kind: 'event', title: 'NT Live: Hamlet', identityStatus: 'event', identityReason: 'a live or staged event, not a film',
      slots: [slot(ODEON, '2026-11-06', 'unclassified', null, '2026-11-06T19:00:00Z')],
    },
  ]
  return { generatedAtUtc: '2026-11-03T16:30:00Z', window: { dateFrom: dates[0], dateTo: dates[13] }, thisWeekTo: dates[6], venues: venues(), films, complete: false }
}

type Showing = CinemaFilmDetail['showings'][number]
export function showingFixture(n: number, venueId: string, startsAtUtc: string, changes: Partial<Showing> = {}): Showing {
  return {
    id: uid(100 + n), venueId, sourceTitle: 'A returning favourite', startsAtUtc, endsAtUtc: null, screen: null, formats: ['Format.Projection.Digital'],
    releaseCategory: 'olderFilm', sourceReleaseDate: null, reissue: null, categoryConfidence: 'verified',
    categoryEvidence: { sourceUrl: null, description: 'UK release 1990 · rerun' }, categoryReason: 'UK release 1990 · rerun', confirmation: 'confirmed',
    lastSeenUtc: '2026-11-03T16:00:00Z', observationStale: false, upstreamAge: 'unknown',
    bookingUrl: venueId === VUE ? `https://www.myvue.com/book-tickets/summary/10097/${String(n)}` : `https://www.odeon.co.uk/ticketing/seat-picker/?showtimeId=615-${String(n)}`,
    ...changes,
  }
}

/** The favourite's page: two cinemas today, IMAX at Vue, and one more at ODEON tomorrow. */
export function detailFixture(): CinemaFilmDetail {
  const list = filmsFixture()
  const film: Partial<Card> = { ...list.films[0] }
  delete film.slots
  return {
    generatedAtUtc: list.generatedAtUtc, window: list.window, thisWeekTo: list.thisWeekTo, film: film as CinemaFilmDetail['film'], venues: list.venues,
    showings: [
      showingFixture(1, VUE, '2026-11-03T20:00:00Z', { formats: ['IMAX'], screen: '4' }),
      showingFixture(2, ODEON, '2026-11-03T21:00:00Z'),
      showingFixture(3, ODEON, '2026-11-04T18:30:00Z', { sourceTitle: 'A returning favourite (35th Anniversary)', categoryReason: 'UK release 1990 · the cinema calls it an anniversary showing · rerun' }),
    ],
    alsoListed: [],
  }
}
