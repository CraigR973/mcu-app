import { describe, expect, it } from 'vitest'
import { fuzzyScore } from './fuzzy'

describe('fuzzyScore', () => {
  it('matches an in-order subsequence regardless of case', () => {
    expect(fuzzyScore('mov', 'Movies')).not.toBeNull()
    expect(fuzzyScore('MOV', 'movies')).not.toBeNull()
  })

  it('rejects a query whose letters are out of order', () => {
    expect(fuzzyScore('ivmo', 'Movies')).toBeNull()
  })

  it('rejects a query containing a letter the target does not have', () => {
    expect(fuzzyScore('moz', 'Movies')).toBeNull()
  })

  it('scores a contiguous prefix match higher than a scattered one', () => {
    // Both are legal subsequences of "Stats" — "sta" runs together at the start,
    // "sts" has to skip the middle "at" to land its last letter.
    const contiguous = fuzzyScore('sta', 'Stats')
    const scattered = fuzzyScore('sts', 'Stats')
    expect(contiguous).not.toBeNull()
    expect(scattered).not.toBeNull()
    expect(contiguous as number).toBeGreaterThan(scattered as number)
  })

  it('treats an empty query as matching everything with the lowest score', () => {
    expect(fuzzyScore('', 'Movies')).toBe(0)
    expect(fuzzyScore('   ', 'Movies')).toBe(0)
  })
})
