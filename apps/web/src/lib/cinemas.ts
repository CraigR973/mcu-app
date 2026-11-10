import type { CinemaFilms, CinemaProgrammeResponse } from '@mcu/shared'
import { formatLondonClock, formatWeekdayDate, londonDate } from './utils'
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
  // AE4 (#355): the tenth, read from CinemaTimes as the four ODEONs are.
  ['Omniplex Glasgow - Renfrew Street', 'https://www.omniplexcinemas.co.uk/cinema/showtimes/glasgow-renfrew-street'],
] as const

const BOOKING_PATHS: Record<string, string[]> = {
  'www.odeon.co.uk': ['/ticketing/seat-picker/', '/cinemas/'],
  'www.omniplexcinemas.co.uk': ['/booking/seats/', '/cinema/'],
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

const FORMAT_LABELS: Record<string, string> = {
  '2d': '2D', '3d': '3D', '4k': '4K', imax: 'IMAX', isense: 'iSense',
  // AE4: the Omniplex's own big screen.
  maxx: 'MAXX',
  'format.projection.3d': '3D', 'format.projection.4k': '4K',
  'format.projection.digital': 'Digital projection', 'format.projection.imax': 'IMAX',
}

/** Preserve source facts while keeping provider enum syntax out of the programme. */
export function showingFormats(values: string[]): string[] {
  return [...new Set(values.map((value) => FORMAT_LABELS[value.toLowerCase()] ?? (/^format\./i.test(value) ? 'Format unverified' : value)))]
}

/** The formats worth a word on a time chip: "Digital projection" is how almost every film is
 *  shown, so the film page says it once for the cinema and the day view not at all. */
export function chipFormats(values: string[]): string[] {
  return showingFormats(values).filter((format) => format !== 'Digital projection')
}

export function showingScreen(value: string): string {
  return /^\d+$/.test(value) ? `Screen ${value}` : value
}

export type ProgrammeFilm = CinemaProgrammeResponse['films'][number]

/** AC3 (#335): `review` waits for Craig's check on Identify films; `event` is never one film. */
export const IDENTITY_LABELS: Record<ProgrammeFilm['identityStatus'], string> = {
  verified: 'Identity verified',
  conflict: 'Programme title differs — check cinema',
  unverified: 'Identity unverified · possible duplicate programme',
  review: 'Identity waiting for a check · possible duplicate programme',
  event: 'An event or double bill, not one film',
}

export function filmIdentity(film: ProgrammeFilm): string {
  if (film.identityStatus === 'event') return IDENTITY_LABELS.event
  const year = film.yearConfidence === 'verified' && film.originalYear !== null ? `Original year ${film.originalYear}` : 'Year unverified'
  return `${year} · ${IDENTITY_LABELS[film.identityStatus]}`
}

/** Why a showing is in its run, in words: AC3's stored reason ("UK release 1975 · rerun"),
 *  also for a linked film left Unclassified, or AB6's quote from the source. */
export function runReason(showing: ProgrammeShowing): string | null {
  const reason = showing.categoryReason ?? (showing.releaseCategory !== 'unclassified' ? showing.categoryEvidence.description : null)
  return reason ? reason.charAt(0).toUpperCase() + reason.slice(1) : null
}

// ---------------------------------------------------------------------------
// AC4 — At the cinema, film first
// ---------------------------------------------------------------------------

export type { CinemaFilms }
export type CinemaCard = CinemaFilms['films'][number]
export type CinemaSlot = CinemaCard['slots'][number]

/** A word or two where a card has room for little more: the film page uses the full name. */
const SHORT_NAMES: Record<string, string> = {
  'odeon-kilmarnock': 'ODEON Kilmarnock',
  'odeon-glasgow-quay': 'ODEON Quay',
  'odeon-braehead': 'ODEON Braehead',
  'odeon-east-kilbride': 'ODEON East Kilbride',
  'cineworld-silverburn': 'Cineworld Silverburn',
  'vue-st-enoch': 'Vue St Enoch',
  'everyman-glasgow': 'Everyman',
  gft: 'GFT',
  'science-centre-imax': 'Science Centre IMAX',
  'omniplex-glasgow-renfrew-street': 'Omniplex Renfrew St',
}

export function shortVenueName(venue: { slug: string; name: string }): string {
  return SHORT_NAMES[venue.slug] ?? venue.name
}

/** What the view is narrowed to; `venueIds` null is every cinema. Kept in the address, so the
 *  view comes back as it was from a film page. */
export interface CinemaFilters { run: ReleaseFilter; day: string | null; venueIds: string[] | null }

/** "19:30", UK time. */
export const clock = formatLondonClock

/** "Sat 8 Nov". */
export const dayAndDate = formatWeekdayDate

/** "Today", "Tomorrow", else "Sat 8": short enough for a card. */
export function shortDay(day: string, today: string): string {
  if (day === today) return 'Today'
  if (day === shiftDate(today, 1)) return 'Tomorrow'
  return formatWeekdayDate(day).replace(/ \w+$/, '')
}

/** "Today · Thu 5 Nov", "Sat 8 Nov": a day's heading on the film page. */
export function dayHeading(day: string, today: string): string {
  const near = day === today ? 'Today' : day === shiftDate(today, 1) ? 'Tomorrow' : null
  return near ? `${near} · ${dayAndDate(day)}` : dayAndDate(day)
}

/** AC3's run in a word: a first run (a preview before the UK release), or a rerun. */
export function runBadge(category: ProgrammeShowing['releaseCategory'], reason: string | null): 'First run' | 'Preview' | 'Rerun' | null {
  if (category === 'newRelease') return reason && /\bpreview\b/i.test(reason) ? 'Preview' : 'First run'
  if (category === 'olderFilm') return 'Rerun'
  return null
}

/** What a card shows under the filters: its showings still to start, where and when next. */
export interface CinemaLine {
  card: CinemaCard
  showings: number
  venueIds: string[]
  firstDay: string
  next: { at: string; venueId: string; day: string }
  run: ProgrammeShowing['releaseCategory']
  runReason: string | null
}

export function cinemaLine(card: CinemaCard, filters: CinemaFilters, now: number, category = filters.run): CinemaLine | null {
  const starts: { at: string; slot: CinemaSlot }[] = []
  for (const slot of card.slots) {
    if (filters.day !== null && slot.localDate !== filters.day) continue
    if (filters.venueIds !== null && !filters.venueIds.includes(slot.venueId)) continue
    if (category !== 'all' && slot.releaseCategory !== category) continue
    for (const at of slot.startsAtUtc) if (Date.parse(at) > now) starts.push({ at, slot })
  }
  if (starts.length === 0) return null
  starts.sort((a, b) => Date.parse(a.at) - Date.parse(b.at))
  const [first] = starts
  return {
    card,
    showings: starts.length,
    venueIds: [...new Set(starts.map(({ slot }) => slot.venueId))],
    firstDay: starts.reduce((day, { slot }) => (slot.localDate < day ? slot.localDate : day), first.slot.localDate),
    next: { at: first.at, venueId: first.slot.venueId, day: first.slot.localDate },
    run: first.slot.releaseCategory,
    runReason: first.slot.runReason,
  }
}

export interface CinemaSections {
  /** Films showing today or in the six days after it. */
  thisWeek: CinemaLine[]
  /** Films whose first showing comes later, as far as the cinemas list. */
  comingUp: CinemaLine[]
  /** Cinemas' own listings not matched to one film yet, title by title. */
  listings: CinemaLine[]
  /** Live and staged events and double bills: never one film. */
  events: CinemaLine[]
  /** Films and listings per run, for the run filter: counted before it, after day and cinema. */
  counts: Record<ReleaseFilter, number>
}

const byTitle = (a: CinemaLine, b: CinemaLine) => a.card.title.localeCompare(b.card.title, 'en-GB') || Date.parse(a.next.at) - Date.parse(b.next.at)

export function cinemaSections(data: CinemaFilms, filters: CinemaFilters, now: number): CinemaSections {
  const counts: Record<ReleaseFilter, number> = { all: 0, newRelease: 0, olderFilm: 0, unclassified: 0 }
  const sections: CinemaSections = { thisWeek: [], comingUp: [], listings: [], events: [], counts }
  for (const card of data.films) {
    for (const run of Object.keys(counts) as ReleaseFilter[]) if (cinemaLine(card, filters, now, run)) counts[run] += 1
    const line = cinemaLine(card, filters, now)
    if (!line) continue
    if (card.kind === 'event') sections.events.push(line)
    else if (card.kind === 'listing') sections.listings.push(line)
    else if (line.firstDay <= data.thisWeekTo) sections.thisWeek.push(line)
    else sections.comingUp.push(line)
  }
  // The widest first this week; what opens soonest first after it.
  sections.thisWeek.sort((a, b) => b.venueIds.length - a.venueIds.length || b.showings - a.showings || byTitle(a, b))
  sections.comingUp.sort((a, b) => a.firstDay.localeCompare(b.firstDay) || b.venueIds.length - a.venueIds.length || byTitle(a, b))
  // Title by title, so one film listed by several chains reads together until it is matched.
  sections.listings.sort(byTitle)
  sections.events.sort(byTitle)
  return sections
}

/** The days a showing still to start falls on, today first. */
export function programmeDays(data: Pick<CinemaFilms, 'films'>, now: number): string[] {
  const days = new Set<string>()
  for (const card of data.films) for (const slot of card.slots) if (slot.startsAtUtc.some((at) => Date.parse(at) > now)) days.add(slot.localDate)
  return [...days].sort()
}

/** The last day a cinema lists, or null when it lists none now. */
export function listedTo(venue: ProgrammeVenue): string | null {
  return venue.coverage.reduce<string | null>((last, day) => (day.observed && (last === null || day.localDate > last) ? day.localDate : last), null)
}

/** Cinemas that list less than the fortnight, grouped by their last listed day, and those
 *  with no current listing at all, with why. GFT and Vue listed two days on 4 Nov. */
export function shortHorizons(data: Pick<CinemaFilms, 'venues' | 'window'>): { to: { day: string; venues: ProgrammeVenue[] }[]; none: ProgrammeVenue[] } {
  const to = new Map<string, ProgrammeVenue[]>()
  const none: ProgrammeVenue[] = []
  for (const venue of data.venues) {
    const last = listedTo(venue)
    if (last === null) none.push(venue)
    else if (last < data.window.dateTo) to.set(last, [...(to.get(last) ?? []), venue])
  }
  return { to: [...to.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([day, venues]) => ({ day, venues })), none }
}

/** Whether a saved check behind these venues is failed or past its freshness limits. */
export function staleCoverage(venues: ProgrammeVenue[], now: number): boolean {
  return venues.some((venue) => venue.coverage.some((day) => day.status === 'failed' || day.status === 'stale'
    || Boolean(day.lastSuccessUtc && now - Date.parse(day.lastSuccessUtc) >= 30 * 3600000)
    || Boolean(day.upstreamUtc && now - Date.parse(day.upstreamUtc) >= 36 * 3600000)))
}

/** What a listing is, in a word or two, where a film would show its run. */
export function listingState(card: Pick<CinemaCard, 'kind' | 'identityStatus'>): string {
  if (card.kind === 'event') return 'Event or double bill'
  if (card.identityStatus === 'review') return 'Waiting for a check'
  if (card.identityStatus === 'conflict') return 'Title differs — check cinema'
  return 'Not matched yet'
}

/** Movie night's At the cinema view, and a film's page under it (AC4). */
export const CINEMA_VIEW_PATH = '/movie-night/cinema'
export function cinemaFilmPath(key: string): string {
  return `${CINEMA_VIEW_PATH}/${key}`
}

// ---------------------------------------------------------------------------
// AE5 (#355, points 4, 8 and 13): the day-by-day view, as the cinema apps have it.
// ---------------------------------------------------------------------------

/** The strip's days: today to the last day any cinema lists, or any showing falls on, inside the
 *  fortnight. */
export function stripDays(data: Pick<CinemaFilms, 'venues' | 'window' | 'films'>, now: number): string[] {
  const today = londonDate(now)
  const last = [...data.venues.map(listedTo), ...programmeDays(data, now)].reduce<string>((to, day) => (day !== null && day > to ? day : to), today)
  const end = last < data.window.dateTo ? last : data.window.dateTo
  const days: string[] = []
  for (let day = today; day <= end; day = shiftDate(day, 1)) days.push(day)
  return days
}

/** The days that have a showing still to start under the run and cinema filters: the rest are
 *  greyed in the strip. */
export function daysShowing(data: CinemaFilms, filters: Pick<CinemaFilters, 'run' | 'venueIds'>, now: number): Set<string> {
  const days = new Set<string>()
  for (const card of data.films) {
    for (const slot of card.slots) {
      if (filters.venueIds !== null && !filters.venueIds.includes(slot.venueId)) continue
      if (filters.run !== 'all' && slot.releaseCategory !== filters.run) continue
      if (slot.startsAtUtc.some((at) => Date.parse(at) > now)) days.add(slot.localDate)
    }
  }
  return days
}

/** One time on a day, as a chip: its format and, while AB7's rule allows, its ticket link. */
export interface DayTime { at: string; formats: string[]; bookingUrl: string | null }

/** One film on a day: its times at each cinema, earliest first. */
export interface DayFilm {
  card: CinemaCard
  byVenue: { venueId: string; times: DayTime[] }[]
  run: ProgrammeShowing['releaseCategory']
  runReason: string | null
}

/**
 * A day's films, each with that day's times grouped by cinema — films only: listings not
 * matched yet and events keep their own folded rows. Times already past are left out, so
 * today shows only what is still to come. The widest film first, then the earliest.
 */
export function dayFilms(data: CinemaFilms, filters: CinemaFilters & { day: string }, now: number): DayFilm[] {
  const found: DayFilm[] = []
  for (const card of data.films) {
    if (card.kind !== 'film') continue
    const byVenue = new Map<string, DayTime[]>()
    let first: CinemaSlot | null = null
    for (const slot of card.slots) {
      if (slot.localDate !== filters.day) continue
      if (filters.venueIds !== null && !filters.venueIds.includes(slot.venueId)) continue
      if (filters.run !== 'all' && slot.releaseCategory !== filters.run) continue
      // A list saved before AE5 has no times: its starts still show, without a link.
      const times = slot.times.length > 0
        ? slot.times.map((time) => ({ at: time.at, formats: time.formats, bookingUrl: time.bookingUrl }))
        : slot.startsAtUtc.map((at) => ({ at, formats: [], bookingUrl: null }))
      const coming = times.filter((time) => Date.parse(time.at) > now)
      if (coming.length === 0) continue
      byVenue.set(slot.venueId, [...(byVenue.get(slot.venueId) ?? []), ...coming])
      if (first === null) first = slot
    }
    if (byVenue.size === 0 || first === null) continue
    found.push({
      card,
      byVenue: [...byVenue].map(([venueId, times]) => ({ venueId, times: times.sort((a, b) => Date.parse(a.at) - Date.parse(b.at)) })),
      run: first.releaseCategory,
      runReason: first.runReason,
    })
  }
  const earliest = (film: DayFilm) => Math.min(...film.byVenue.map((venue) => Date.parse(venue.times[0].at)))
  return found.sort((a, b) => b.byVenue.length - a.byVenue.length || earliest(a) - earliest(b) || a.card.title.localeCompare(b.card.title, 'en-GB'))
}

/** A time's ticket link under AB7's rule, checked again here as the saved view ages: only when
 *  connected, before it starts, with the cinema switched on and its day's listing fresh. */
export function timeBooking(time: DayTime, venue: ProgrammeVenue, now: number, connected: boolean): string | null {
  const url = safeUrl(time.bookingUrl)
  const coverage = venue.coverage.find((date) => date.localDate === londonDate(Date.parse(time.at)))
  if (!connected || !venue.collectionEnabled || !coverage?.observed || coverage.status === 'failed' || coverage.status === 'stale'
    || !coverage.lastSuccessUtc || now - Date.parse(coverage.lastSuccessUtc) >= 30 * 60 * 60 * 1000
    || (coverage.upstreamUtc !== null && now - Date.parse(coverage.upstreamUtc) >= 36 * 60 * 60 * 1000)
    || Date.parse(time.at) <= now) return null
  return url && BOOKING_PATHS[url.hostname]?.some((path) => url.pathname.startsWith(path)) ? time.bookingUrl : null
}

