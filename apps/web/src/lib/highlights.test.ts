import { describe, expect, it } from 'vitest'

import { stars, whoseRatings } from './highlights'

describe('Highlights words — Batch V5', () => {
  it('writes ratings on the half-star scale', () => {
    expect(stars(5)).toBe('5')
    expect(stars(4.5)).toBe('4½')
    expect(stars(0.5)).toBe('0½')
  })

  it('says whose ratings they are, and who has rated none (#159)', () => {
    expect(whoseRatings(['Craig'], ['Mark'])).toBe('Rated 4½ or 5 stars by Craig. Mark has not rated any films.')
    expect(whoseRatings(['Craig', 'Mark'], [])).toBe('Rated 4½ or 5 stars by Craig and Mark.')
    expect(whoseRatings(['Craig'], ['Mark', 'Sam'])).toBe(
      'Rated 4½ or 5 stars by Craig. Mark and Sam have not rated any films.',
    )
  })
})
