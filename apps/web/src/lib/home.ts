/** Small rules for Home's rows — Batch W2. Kept apart from the components, which each export one. */

import type { CompletionSet } from '@mcu/shared'

/**
 * Completion's cards, closest to complete first (#249): the sets with the fewest films
 * missing lead, since one or two more discs would finish them; a finished set follows the
 * unfinished ones; ties go to the higher share, then the name.
 */
export function closestToComplete(sets: CompletionSet[]): CompletionSet[] {
  return [...sets].sort((a, b) => {
    const aDone = a.missingCount === 0
    const bDone = b.missingCount === 0
    if (aDone !== bDone) return aDone ? 1 : -1
    if (a.missingCount !== b.missingCount) return a.missingCount - b.missingCount
    if (a.percentComplete !== b.percentComplete) return b.percentComplete - a.percentComplete
    return a.setName.localeCompare(b.setName)
  })
}

/** "A year ago", "3 years ago": On this day's line under each poster. */
export function yearsAgo(years: number): string {
  return years === 1 ? 'A year ago' : `${String(years)} years ago`
}
