import { describe, expect, it } from 'vitest'

import { addedLine, stars, whoseRatings } from './highlights'

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

describe('Recently added words — AE2 (#355)', () => {
  const TODAY = '2026-11-09'

  it('names who added the copy, the day, and what it is', () => {
    expect(addedLine({ addedBy: 'Mark', addedAt: '2026-11-05T20:26:00Z', formats: ['4k_uhd'] }, TODAY)).toBe('Mark · 5 Nov · 4K UHD')
  })

  it('names a combo best first, whichever format was ticked first', () => {
    expect(addedLine({ addedBy: 'Craig', addedAt: '2026-10-10T19:00:00Z', formats: ['blu_ray', '4k_uhd'] }, TODAY)).toBe(
      'Craig · 10 Oct · 4K UHD + Blu-ray',
    )
  })

  it('reads the day in London, and shows the year only when it is not this one', () => {
    // 23:30 UTC on 1 Jul is 00:30 on 2 Jul in London.
    expect(addedLine({ addedBy: 'Mark', addedAt: '2026-07-01T23:30:00Z', formats: ['dvd'] }, TODAY)).toBe('Mark · 2 Jul · DVD')
    expect(addedLine({ addedBy: 'Mark', addedAt: '2025-12-30T12:00:00Z', formats: ['dvd'] }, TODAY)).toBe('Mark · 30 Dec 2025 · DVD')
  })

  it('names nobody when the person who added it has gone', () => {
    expect(addedLine({ addedBy: null, addedAt: '2026-11-05T20:26:00Z', formats: ['download'] }, TODAY)).toBe('Added 5 Nov · Digital')
  })
})
