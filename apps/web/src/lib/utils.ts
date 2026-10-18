import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/**
 * A calendar date as a person in the UK writes it: `2025-03-12` → "12 Mar 2025".
 *
 * Read straight off the string rather than through `Date`, for two reasons.
 * `new Date('2025-03-12')` is midnight UTC, which west of Greenwich is the evening before,
 * so a watch logged on the 12th would read the 11th. And `toLocaleDateString('en-GB')`
 * abbreviates September as "Sept" in some browsers and "Sep" in others.
 */
export function formatShortDate(isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day || month > 12) return isoDate
  return `${String(day)} ${MONTHS[month - 1]} ${String(year)}`
}

/** The same date without its year, for something recent: "30 Sep" (Batch X1's "Seen 30 Sep"). */
export function formatDayMonth(isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day || month > 12) return isoDate
  return `${String(day)} ${MONTHS[month - 1]}`
}

function dateParts(value: string | Date): { year: number; month: number; day: number } | null {
  // A bare `YYYY-MM-DD` is read off the string, never through `Date`, for the reason
  // `formatShortDate` gives. A timestamp is a moment: it reads in the viewer's own day.
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number)
    return year && month && day && month <= 12 ? { year, month, day } : null
  }
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return { year: date.getFullYear(), month: date.getMonth() + 1, day: date.getDate() }
}

/**
 * The one way a date reads on a screen (Batch X12a, UX48-05): "11 Oct" in the current year,
 * "11 Oct 2026" in any other. The review found four forms on one phone ("11/10/2026",
 * "24 Sep 2026", "22 Sept", "2026-09"), two of them from `toLocaleDateString`, whose output
 * differs by browser and locale.
 */
export function formatDate(value: string | Date, now: Date = new Date()): string {
  const parts = dateParts(value)
  if (!parts) return typeof value === 'string' ? value : ''
  const base = `${String(parts.day)} ${MONTHS[parts.month - 1]}`
  return parts.year === now.getFullYear() ? base : `${base} ${String(parts.year)}`
}

/** A moment: "11 Oct, 14:32" in the viewer's own time. */
export function formatDateTime(value: string | Date, now: Date = new Date()): string {
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return typeof value === 'string' ? value : ''
  const time = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  return `${formatDate(date, now)}, ${time}`
}

/** A month as the spend chart labels it: `2026-09` → "Sep 2026". */
export function formatMonth(month: string): string {
  const [year, number] = month.split('-').map(Number)
  if (!year || !number || number > 12) return month
  return `${MONTHS[number - 1]} ${String(year)}`
}
