/** Words for Home's Highlights — Batch V5. Kept apart from the component, which exports one. */

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
