import { FORMATS } from '@/lib/api'

/**
 * AE1 (#355, point 10): what a copy's formats mean.
 *
 * A copy is one physical item, so two disc formats on one copy say "one box holding both
 * discs", a combo pack. Mark ticked 4K UHD on Contagion's Blu-ray copy on 4 Nov meaning "I
 * bought the 4K too", and got one combo copy. The edit form now asks which he means before
 * it saves, and these are the rules it asks by.
 */

/** The formats that are a disc in a box. Digital is not: a download sits beside a disc
 *  without making the box a combo, so ticking it never asks. */
export const DISC_FORMATS: readonly string[] = ['4k_uhd', 'blu_ray', 'dvd']

export function isDiscFormat(code: string): boolean {
  return DISC_FORMATS.includes(code)
}

/**
 * The disc formats an edit adds to a copy, when the edit leaves the copy holding two or
 * more of them. Empty when there is nothing to ask: no disc added, or a swap from one disc
 * format to another (correcting a Blu-ray that is really a DVD is not a second disc).
 */
export function addedDiscFormats(before: readonly string[], after: readonly string[]): string[] {
  const discsAfter = after.filter(isDiscFormat)
  if (discsAfter.length < 2) return []
  return discsAfter.filter((code) => !before.includes(code))
}

/** Real formats only, once each, best first: the form's own order, so a combo reads
 *  "4K UHD and Blu-ray" whichever was ticked first. */
export function inFormOrder(values: readonly string[]): string[] {
  return FORMATS.map((format) => format.value).filter((code) => values.includes(code))
}

/** The formats named in an address. Anything that is not a real format is ignored rather
 *  than trusted. */
export function formatsFromParams(values: readonly string[]): string[] {
  return inFormOrder(values)
}

/** Where "a separate copy" goes: Add a copy for the same film with the new format chosen. */
export function addCopyPath(movieId: string, formats: readonly string[] = []): string {
  const params = new URLSearchParams({ movie: movieId })
  for (const code of formats) params.append('format', code)
  return `/collection/add?${params.toString()}`
}
