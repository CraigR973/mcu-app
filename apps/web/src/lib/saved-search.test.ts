import { describe, expect, it } from 'vitest'

import { readSavedSearch, wordsNameFilm } from './saved-search'

describe('reading an eBay saved search — Batch T8b', () => {
  it('takes the format from the words that name it, and leaves the rest to find the film', () => {
    expect(readSavedSearch('dog soldiers 4k')).toEqual({ words: 'dog soldiers', format: '4k_uhd' })
    expect(readSavedSearch('Heat Blu-ray')).toEqual({ words: 'heat', format: 'blu_ray' })
    expect(readSavedSearch('alien bluray')).toEqual({ words: 'alien', format: 'blu_ray' })
    expect(readSavedSearch('Predator DVD region 2')).toEqual({ words: 'predator region 2', format: 'dvd' })
    expect(readSavedSearch('the thing Ultra HD')).toEqual({ words: 'the thing', format: '4k_uhd' })
  })

  it('reads "4K UHD Blu-ray", how 4K discs are sold, as 4K, and takes out every format word', () => {
    expect(readSavedSearch('Dog Soldiers 4K UHD Blu-ray')).toEqual({ words: 'dog soldiers', format: '4k_uhd' })
  })

  it('leaves edition words, which can be title words, and says nothing of a format it was not given', () => {
    expect(readSavedSearch('The Collector steelbook')).toEqual({ words: 'the collector steelbook', format: null })
  })

  it("keeps a title's own letters and digits", () => {
    expect(readSavedSearch('Amélie 4K')).toEqual({ words: 'amélie', format: '4k_uhd' })
    expect(readSavedSearch("Se7en (1995) collector's")).toEqual({ words: 'se7en 1995 collectors', format: null })
  })
})

describe('whether search words name a film — Batch T8b', () => {
  it('needs every word of the title, a leading article aside', () => {
    expect(wordsNameFilm('dog soldiers steelbook', 'Dog Soldiers')).toBe(true)
    expect(wordsNameFilm('thing arrow', 'The Thing')).toBe(true)
    expect(wordsNameFilm('the thing', 'The Thing')).toBe(true)
    expect(wordsNameFilm('dog', 'Dog Soldiers')).toBe(false)
    expect(wordsNameFilm('aliens', 'Alien')).toBe(false)
  })

  it('matches across punctuation and case, and never on an empty title', () => {
    expect(wordsNameFilm("schindlers list", "Schindler's List")).toBe(true)
    expect(wordsNameFilm('anything', '')).toBe(false)
  })
})
