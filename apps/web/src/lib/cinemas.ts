import type { CinemaProgrammeResponse } from '@mcu/shared'
import { londonDate } from './utils'
export { londonDate, formatLondonDateTime as londonTime } from './utils'

export type ProgrammeVenue = CinemaProgrammeResponse['venues'][number]
export type ProgrammeShowing = CinemaProgrammeResponse['films'][number]['showings'][number]
export type ReleaseFilter = 'all' | ProgrammeShowing['releaseCategory']

export const RELEASE_LABELS: Record<ReleaseFilter, string> = {
  all: 'All films', newRelease: 'New releases', olderFilm: 'Older films', unclassified: 'Unclassified',
}

// Public fallbacks remain usable even when the first stored-programme read fails.
export const OFFICIAL_PROGRAMMES = [
  ['ODEON Kilmarnock', 'https://www.odeon.co.uk/cinemas/kilmarnock/'],
  ['ODEON Glasgow Quay', 'https://www.odeon.co.uk/cinemas/glasgow-quay/'],
  ['ODEON Braehead', 'https://www.odeon.co.uk/cinemas/braehead/'],
  ['ODEON East Kilbride', 'https://www.odeon.co.uk/cinemas/east-kilbride/'],
  ['Cineworld Glasgow Silverburn', 'https://www.cineworld.co.uk/cinemas/glasgow-silverburn'],
  ['Vue Glasgow St Enoch', 'https://www.myvue.com/cinema/glasgow-st-enoch/whats-on'],
  ['Everyman Glasgow', 'https://www.everymancinema.com/venues-list/x11dq-everyman-glasgow/'],
  ['Glasgow Film Theatre', 'https://www.glasgowfilm.org/all-listings/'],
  ['Glasgow Science Centre IMAX', 'https://www.glasgowsciencecentre.org/imax'],
] as const

const BOOKING_PATHS: Record<string, string[]> = {
  'www.odeon.co.uk': ['/ticketing/seat-picker/', '/cinemas/'],
  'www.myvue.com': ['/book-tickets/', '/cinema/'],
  'www.everymancinema.com': ['/booking/', '/venues-list/', '/film-listing/'],
  'purchase.everymancinema.com': ['/launch/ticketing/'],
  'web.cineworld.co.uk': ['/order/showtimes/'],
  'www.cineworld.co.uk': ['/cinemas/'],
  'www.glasgowfilm.org': ['/checkout/showing/', '/movie/', '/all-listings/'],
  'www.tickettailor.com': ['/events/gscimax/'],
  'buytickets.at': ['/gscimax/'],
}
const PROGRAMME_HOSTS = new Set([
  ...Object.keys(BOOKING_PATHS), 'cinematimes.com', 'www.glasgowsciencecentre.org',
])

function safeUrl(value: string | null): URL | null {
  if (!value || value.length > 2048 || Array.from(value).some((character) => character.charCodeAt(0) < 32)) return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password && (!url.port || url.port === '443') ? url : null
  } catch { return null }
}

export function programmeUrl(value: string): string | null {
  const url = safeUrl(value)
  return url && PROGRAMME_HOSTS.has(url.hostname) ? value : null
}

export function shiftDate(day: string, by: number): string {
  const value = new Date(`${day}T12:00:00Z`)
  value.setUTCDate(value.getUTCDate() + by)
  return value.toISOString().slice(0, 10)
}

export function showingBooking(showing: ProgrammeShowing, venue: ProgrammeVenue, now: number, connected: boolean): string | null {
  const url = safeUrl(showing.bookingUrl)
  const coverage = venue.coverage.find((date) => date.localDate === londonDate(Date.parse(showing.startsAtUtc)))
  const seen = Date.parse(showing.lastSeenUtc)
  if (!connected || !venue.collectionEnabled || !coverage?.observed || coverage.status === 'failed' || coverage.status === 'stale'
    || !coverage.lastSuccessUtc || now - Date.parse(coverage.lastSuccessUtc) >= 30 * 60 * 60 * 1000
    || (coverage.upstreamUtc !== null && now - Date.parse(coverage.upstreamUtc) >= 36 * 60 * 60 * 1000)
    || showing.confirmation !== 'confirmed' || showing.observationStale || showing.upstreamAge === 'stale'
    || !Number.isFinite(seen) || seen > now || now - seen >= 30 * 60 * 60 * 1000 || Date.parse(showing.startsAtUtc) <= now) return null
  return url && BOOKING_PATHS[url.hostname]?.some((path) => url.pathname.startsWith(path)) ? showing.bookingUrl : null
}

export const COVERAGE_LABELS: Record<ProgrammeVenue['coverage'][number]['status'], string> = {
  notEnabled: 'Collection paused', unavailable: 'Programme not checked', failed: 'Latest check failed',
  empty: 'Checked: no showings', partial: 'Partial programme', healthy: 'Checked programme', stale: 'Saved programme is stale',
}
