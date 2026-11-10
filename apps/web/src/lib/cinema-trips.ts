import type { CinemaFilmDetail, CinemaTrip, NeedsYouTripItem, NextScreening, NextTrip, TripReply, TripShowingFlag } from '@mcu/shared'

import { showingFormats, type ProgrammeShowing, type ProgrammeVenue } from './cinemas'
import { describeError, classifyError } from './describe-error'
import { formatLondonClock, formatWeekdayDate, londonDate } from './utils'

/**
 * Cinema trips in words — AC5 (#345). The wording Craig approved, in one place: a trip's time,
 * its replies, the flag the live programme raises, Needs you's items and Home's top slot.
 *
 * Times are the cinema's own (UK), as the film page writes them: every one is in Europe/London.
 */

/** Every push, card and Needs you item opens the trip's own page. */
export function tripPath(id: string): string {
  return `/movie-night/trips/${id}`
}

/** "Mon 9 Nov 20:10". */
export function tripWhen(startsAtUtc: string): string {
  return `${formatWeekdayDate(londonDate(Date.parse(startsAtUtc)))} ${formatLondonClock(startsAtUtc)}`
}

/** Formats worth a word after a time, "IMAX" or "IMAX · 3D"; plain digital says nothing. */
export function tripFormats(formats: string[]): string {
  return showingFormats(formats).filter((format) => format !== 'Digital projection').join(' · ')
}

/** "20:00 IMAX": a time with its formats, as a time chip says it. */
export function tripClock(startsAtUtc: string, formats: string[] = []): string {
  const words = tripFormats(formats)
  return words ? `${formatLondonClock(startsAtUtc)} ${words}` : formatLondonClock(startsAtUtc)
}

/** "Mon 9 Nov · 20:10 · ODEON Glasgow Quay": a trip's card line. */
export function tripLine(showing: Pick<CinemaTrip['showing'], 'startsAtUtc' | 'formats' | 'venueName'>): string {
  const day = formatWeekdayDate(londonDate(Date.parse(showing.startsAtUtc)))
  return `${day} · ${tripClock(showing.startsAtUtc, showing.formats)} · ${showing.venueName}`
}

/** A reply as the trip page and the cards say it. Invited reads "No reply yet". */
export const REPLY_LABELS: Record<TripReply, string> = {
  invited: 'No reply yet',
  going: 'Going',
  notGoing: 'Not going',
  anotherTime: 'Another time',
}

/** "1 going · 1 no reply yet": the proposer counts as going. */
export function tripTally(counts: CinemaTrip['counts']): string {
  return [
    `${String(counts.going)} going`,
    counts.notGoing ? `${String(counts.notGoing)} not going` : null,
    counts.anotherTime ? `${String(counts.anotherTime)} another time` : null,
    counts.invited ? `${String(counts.invited)} no reply yet` : null,
  ].filter(Boolean).join(' · ')
}

/** What the live programme says about the trip's time (#345 §3), and what the proposer is
 *  asked to do about it. */
export function flagWords(flag: TripShowingFlag, venueName: string): { line: string; ask: string | null } {
  if (flag === 'unconfirmed') return { line: `Not on ${venueName}’s latest listing. It may have been withdrawn.`, ask: null }
  if (flag === 'cancelled') return { line: `${venueName} has cancelled this showing.`, ask: 'Pick another time or cancel.' }
  return { line: `${venueName} no longer lists this time.`, ask: 'Pick another time or cancel.' }
}

/** A trip item in Needs you, and where it goes: always the trip's own page (#345 §6). */
export function tripNeedsYouCopy(item: NeedsYouTripItem): { title: string; detail: string; to: string } {
  const to = tripPath(item.tripId)
  const when = tripWhen(item.startsAtUtc)
  if (item.kind === 'tripInvite') {
    return { title: `${item.proposerName} invited you: ${item.filmTitle}, ${when}`, detail: item.venueName, to }
  }
  if (item.kind === 'tripSuggestion') {
    return { title: `${item.fromName ?? 'Someone'} suggests another time for ${item.filmTitle}`, detail: `${when} · ${item.venueName}`, to }
  }
  return { title: `${item.venueName} no longer lists your ${item.filmTitle} time`, detail: 'Pick another time or cancel.', to }
}

/** AE8 (#355): another keeper's trip item, as the reader reads it: theirs to act on, the trip
 *  open to read. ``you`` is the reader's own name, for a suggestion the reader made. */
export function othersTripCopy(item: NeedsYouTripItem, owner: string, you: string | undefined): { title: string; detail: string; to: string } {
  const to = tripPath(item.tripId)
  const when = tripWhen(item.startsAtUtc)
  if (item.kind === 'tripInvite') {
    return { title: `${owner} hasn’t replied: ${item.filmTitle}, ${when}`, detail: item.venueName, to }
  }
  if (item.kind === 'tripSuggestion') {
    const who = item.fromName && item.fromName === you ? 'You suggest' : `${item.fromName ?? 'Someone'} suggests`
    return { title: `${who} another time for ${item.filmTitle}`, detail: `${owner} to answer · ${when} · ${item.venueName}`, to }
  }
  return { title: `${item.venueName} no longer lists ${owner}’s ${item.filmTitle} time`, detail: `${owner} picks another time or cancels.`, to }
}

/** Home's top slot: "Next: Wild Horse Nine, Mon 9 Nov 20:10 at ODEON Glasgow Quay, with Mark". */
export function nextTripWords(trip: NextTrip): { detail: string; sentence: string } {
  const company = trip.withNames.length ? `, with ${trip.withNames.join(' and ')}` : ''
  const detail = `${tripWhen(trip.startsAtUtc)} at ${trip.venueName}${company}`
  return { detail, sentence: `Next: ${trip.filmTitle}, ${detail}` }
}

/** The top slot shows the next trip when it is sooner than the next planned screening. */
export function tripIsSooner(trip: NextTrip | null, screening: NextScreening | null): trip is NextTrip {
  return trip !== null && (screening === null || Date.parse(trip.startsAtUtc) < Date.parse(screening.plannedStart))
}

/** Trip writes are online only (#345 §2): they never join the offline queue. */
export const TRIP_OFFLINE = 'You’re offline. Reply when you have signal.'

/** A failed trip write in words: the API's own sentence for a refusal ("The trip has moved…"),
 *  and the offline line for no signal. */
export function tripErrorMessage(error: unknown, fallback: string): string {
  return classifyError(error) === 'offline' ? TRIP_OFFLINE : describeError(error, fallback)
}

/** The trips that belong on a film's page: its own address, or a showing on the page, so a trip
 *  proposed on a listing still shows once a morning links the film. */
export function tripsForFilm(trips: CinemaTrip[], key: string, showingIds: ReadonlySet<string>): CinemaTrip[] {
  return trips.filter((trip) => trip.filmKey === key || (trip.showing.showingId !== null && showingIds.has(trip.showing.showingId)))
}

export interface TripDay { day: string; cinemas: { venue: ProgrammeVenue; showings: ProgrammeShowing[] }[] }

/** The film page's times that a trip can take: confirmed and still to start (#345 §2), by day
 *  then cinema in the order each first shows that day. Unconfirmed and started ones cannot be
 *  proposed, suggested or moved to. */
export function pickableTimes(detail: CinemaFilmDetail, now: number, exclude?: string | null): TripDay[] {
  const venues = new Map(detail.venues.map((venue) => [venue.id, venue]))
  const days = new Map<string, Map<string, { venue: ProgrammeVenue; showings: ProgrammeShowing[] }>>()
  for (const showing of detail.showings) {
    const venue = venues.get(showing.venueId)
    if (!venue || showing.id === exclude || showing.confirmation !== 'confirmed' || Date.parse(showing.startsAtUtc) <= now) continue
    const day = londonDate(Date.parse(showing.startsAtUtc))
    const cinemas = days.get(day) ?? new Map()
    const group = cinemas.get(venue.id) ?? { venue, showings: [] }
    group.showings.push(showing)
    cinemas.set(venue.id, group)
    days.set(day, cinemas)
  }
  return [...days.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([day, cinemas]) => ({ day, cinemas: [...cinemas.values()] }))
}
