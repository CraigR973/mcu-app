import type { CalendarEntry } from '@mcu/shared'

/** The two `RELEASE_TYPES` members that mean "on a disc". */
const PHYSICAL_TYPES = new Set(['4k_uhd_release', 'blu_ray_release'])

export function isPhysical(entry: CalendarEntry): boolean {
  return PHYSICAL_TYPES.has(entry.releaseType)
}

/** Six months ahead, the window the API ingests (Batch T5). */
export const DISC_WINDOW_DAYS = 183
