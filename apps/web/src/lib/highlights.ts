/** Words for Home's Highlights — Batch V5. Kept apart from the component, which exports one. */

import { formatLabel } from '@/lib/api'
import { inFormOrder } from '@/lib/copy-formats'
import { formatDayMonth, formatShortDate, londonDate } from '@/lib/utils'

/** 4.5 → "4½", 5 → "5": the half-star scale ratings are kept on. */
export function stars(rating: number): string {
  const whole = Math.floor(rating)
  return rating - whole >= 0.5 ? `${String(whole)}½` : String(whole)
}

/** "Craig", "Craig and Mark", "Craig, Mark and Sam". */
function names(people: string[]): string {
  if (people.length <= 1) return people.join('')
  return `${people.slice(0, -1).join(', ')} and ${people[people.length - 1]}`
}

/**
 * Whose ratings the row shows — Craig rates on Letterboxd and Mark does not (#159), so the
 * row says so rather than implying both.
 */
export function whoseRatings(ratedBy: string[], notRatedBy: string[]): string {
  const rated = `Rated 4½ or 5 stars by ${names(ratedBy)}`
  if (notRatedBy.length === 0) return `${rated}.`
  return `${rated}. ${names(notRatedBy)} ${notRatedBy.length === 1 ? 'has' : 'have'} not rated any films.`
}

/**
 * "Mark · 5 Nov · 4K UHD": who added a copy, the day it was added in London, and what it is —
 * AE2 (#355). The year shows only when it is not this one; a copy whose adder has gone reads
 * "Added 5 Nov".
 */
export function addedLine(film: { addedBy: string | null; addedAt: string; formats: string[] }, today = londonDate()): string {
  const day = londonDate(Date.parse(film.addedAt))
  const when = day.slice(0, 4) === today.slice(0, 4) ? formatDayMonth(day) : formatShortDate(day)
  const what = inFormOrder(film.formats).map((code) => formatLabel(code) ?? code).join(' + ')
  return [film.addedBy ? `${film.addedBy} · ${when}` : `Added ${when}`, what].filter(Boolean).join(' · ')
}
