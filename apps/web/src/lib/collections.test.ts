import { describe, expect, it } from 'vitest'
import type { SmartCollectionFilters } from '@mcu/shared'

import { completionLabel, describeFilters, filtersToMovieFilters } from './api'

const NO_FILTERS: SmartCollectionFilters = {
  genreId: null,
  year: null,
  format: null,
  section: null,
  shelf: null,
  decadeFrom: null,
  decadeTo: null,
  minRating: null,
  watched: null,
}

describe('completionLabel', () => {
  it('reads as §11.4 words it', () => {
    expect(completionLabel({ ownedCount: 3, expectedCount: 4 })).toBe('3 of 4')
  })

  it('says how many discs it has when the box size is unknown', () => {
    // Never "3 of 0" and never "incomplete": an unrecorded expected count is a fact
    // nobody entered, not a judgement about the set.
    expect(completionLabel({ ownedCount: 3, expectedCount: null })).toBe('3 discs')
    expect(completionLabel({ ownedCount: 1, expectedCount: null })).toBe('1 disc')
  })
})

describe('describeFilters', () => {
  it('describes the acceptance criterion’s own collection', () => {
    expect(
      describeFilters({
        ...NO_FILTERS,
        format: '4k_uhd',
        decadeFrom: 2010,
        decadeTo: 2010,
        watched: false,
      }),
    ).toBe('unwatched · 4K UHD · 2010s')
  })

  it('spans a decade range', () => {
    expect(describeFilters({ ...NO_FILTERS, decadeFrom: 1940, decadeTo: 1960 })).toBe(
      '1940s–1960s',
    )
    expect(describeFilters({ ...NO_FILTERS, decadeFrom: 1990 })).toBe('1990s onwards')
    expect(describeFilters({ ...NO_FILTERS, decadeTo: 1950 })).toBe('up to the 1950s')
  })

  it('names a place the way the collection views do', () => {
    expect(describeFilters({ ...NO_FILTERS, section: 'Front', shelf: '2nd' })).toBe('Front 2nd')
  })

  it('says what an unconstrained collection selects rather than nothing', () => {
    // An empty filter set is a legitimate saved collection — "Everything" — and a blank
    // line under its name would read as a broken row.
    expect(describeFilters(NO_FILTERS)).toBe('Everything in the collection')
  })
})

describe('filtersToMovieFilters', () => {
  it('drops the nulls the filter bar expects to be absent', () => {
    expect(
      filtersToMovieFilters({ ...NO_FILTERS, format: '4k_uhd', watched: false }),
    ).toEqual({ format: '4k_uhd', watched: false })
  })

  it('keeps a falsy filter that means something', () => {
    // `watched: false` and `minRating: 0` are real constraints. A truthiness check here
    // would silently turn "unwatched" into "any".
    const out = filtersToMovieFilters({ ...NO_FILTERS, minRating: 0, watched: false })
    expect(out.minRating).toBe(0)
    expect(out.watched).toBe(false)
  })
})
