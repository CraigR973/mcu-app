import { describe, expect, it } from 'vitest'

import { placeLabel } from './place'

describe('placeLabel', () => {
  it('says the recorded place once, not the section and shelf beside it', () => {
    expect(placeLabel({ location: 'Front 4th Shelf', section: 'Front', shelf: '4th' })).toBe('Front 4th Shelf')
  })

  it('files a copy with no recorded place under its section and shelf', () => {
    expect(placeLabel({ location: null, section: 'Front', shelf: '4th' })).toBe('Front · 4th shelf')
    expect(placeLabel({ location: null, section: 'Lounge', shelf: null })).toBe('Lounge')
  })

  it('says so when nothing is recorded', () => {
    expect(placeLabel({ location: null, section: null, shelf: null })).toBe('No place recorded')
  })
})
