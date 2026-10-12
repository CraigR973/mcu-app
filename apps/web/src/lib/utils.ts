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
