import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

/**
 * A calendar date as a person in the UK writes it: `2025-03-12` → "12 Mar 2025".
 *
 * Parsed as a *local* date on purpose. `new Date('2025-03-12')` is midnight UTC, which
 * west of Greenwich is the evening before — a watch logged on the 12th would read the 11th.
 */
export function formatShortDate(isoDate: string): string {
  const [year, month, day] = isoDate.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return isoDate
  return new Date(year, month - 1, day).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}
