import type { CalendarEntry, ReleaseType } from '@mcu/shared'

import { cinemaLine, type CinemaFilms } from './cinemas'

/** The two `RELEASE_TYPES` members that mean "on a disc". */
const PHYSICAL_TYPES = new Set(['4k_uhd_release', 'blu_ray_release'])

export function isPhysical(entry: CalendarEntry): boolean {
  return PHYSICAL_TYPES.has(entry.releaseType)
}

/** Six months ahead, the window the API ingests (Batch T5). */
export const DISC_WINDOW_DAYS = 183

// ---------------------------------------------------------------------------
// AC7 — two calendars, discs and cinemas
// ---------------------------------------------------------------------------

/** Releases' two calendars (#343): `/calendar` and `/calendar/cinema`. */
export type ReleaseCalendar = 'disc' | 'cinema'

/** The release types each calendar's month reads. Streaming and award entries belong to
 *  neither: nothing writes them, and the all-types feed keeps them. */
export const CALENDAR_TYPES: Record<ReleaseCalendar, readonly ReleaseType[]> = {
  disc: ['4k_uhd_release', 'blu_ray_release', 'sale_event'],
  cinema: ['theatrical'],
}

export const CALENDAR_PATHS: Record<ReleaseCalendar, string> = { disc: '/calendar', cinema: '/calendar/cinema' }

/** What the disc calendar's month is narrowed to, kept in the address as `show`. */
export type DiscFilter = 'all' | '4k' | 'blu-ray' | 'sales'

export const DISC_FILTERS: { value: DiscFilter; label: string; types: readonly ReleaseType[] }[] = [
  { value: 'all', label: 'All', types: CALENDAR_TYPES.disc },
  { value: '4k', label: '4K UHD', types: ['4k_uhd_release'] },
  { value: 'blu-ray', label: 'Blu-ray', types: ['blu_ray_release'] },
  { value: 'sales', label: 'Sale events', types: ['sale_event'] },
]

export function discFilter(value: string | null): DiscFilter {
  return DISC_FILTERS.find((filter) => filter.value === value)?.value ?? 'all'
}

/** `YYYY-MM` from the address, when it is a real month the API will answer for. */
export function readMonth(value: string | null): string | null {
  if (!value || !/^\d{4}-\d{2}$/.test(value)) return null
  const [year, month] = value.split('-').map(Number)
  return year >= 1900 && year <= 2200 && month >= 1 && month <= 12 ? value : null
}

/** A cinema release showing at one of the nine: AC4's film page, and how many cinemas. */
export interface CinemaShowing {
  key: string
  venues: number
}

/**
 * Which cinema releases are showing at one of the nine, by TMDB id (#343).
 *
 * A release is showing when AC4's fortnight holds a film, one TMDB film across the cinemas, with
 * this id and a showing still to start. **Never on a title**: a listing not matched to a film
 * yet stays unlinked until a morning matches it (#327, #342).
 */
export function showingAtCinemas(data: CinemaFilms | undefined, now: number): Map<number, CinemaShowing> {
  const showing = new Map<number, CinemaShowing>()
  for (const card of data?.films ?? []) {
    if (card.kind !== 'film' || card.tmdbId === null) continue
    const line = cinemaLine(card, { run: 'all', day: null, venueIds: null }, now)
    if (line) showing.set(card.tmdbId, { key: card.key, venues: line.venueIds.length })
  }
  return showing
}

/** The cinemas' listings not matched to one film yet that still have a showing to start. */
export function unmatchedListings(data: CinemaFilms | undefined, now: number): number {
  return (data?.films ?? []).filter(
    (card) => card.kind === 'listing' && cinemaLine(card, { run: 'all', day: null, venueIds: null }, now) !== null,
  ).length
}
