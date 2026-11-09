import { describe, expect, it } from 'vitest'

import { addCopyPath, addedDiscFormats, formatsFromParams, inFormOrder, isDiscFormat } from './copy-formats'

describe('copy formats — AE1', () => {
  it('counts 4K UHD, Blu-ray and DVD as discs, and Digital as not one', () => {
    expect(['4k_uhd', 'blu_ray', 'dvd'].every(isDiscFormat)).toBe(true)
    expect(isDiscFormat('download')).toBe(false)
  })

  it('names the disc a second disc format adds: Contagion’s 4K ticked on its Blu-ray copy', () => {
    expect(addedDiscFormats(['blu_ray'], ['blu_ray', '4k_uhd'])).toEqual(['4k_uhd'])
  })

  it('asks nothing for a swap from one disc to another, or for a single disc', () => {
    expect(addedDiscFormats(['blu_ray'], ['4k_uhd'])).toEqual([])
    expect(addedDiscFormats([], ['dvd'])).toEqual([])
  })

  it('asks nothing when the addition is digital', () => {
    expect(addedDiscFormats(['blu_ray'], ['blu_ray', 'download'])).toEqual([])
    expect(addedDiscFormats(['4k_uhd', 'blu_ray'], ['4k_uhd', 'blu_ray', 'download'])).toEqual([])
  })

  it('asks nothing for a combo that was already a combo, and asks for a third disc', () => {
    expect(addedDiscFormats(['4k_uhd', 'blu_ray'], ['4k_uhd', 'blu_ray'])).toEqual([])
    expect(addedDiscFormats(['4k_uhd', 'blu_ray'], ['4k_uhd', 'blu_ray', 'dvd'])).toEqual(['dvd'])
  })

  it('puts formats best first, whichever was ticked first', () => {
    expect(inFormOrder(['blu_ray', '4k_uhd'])).toEqual(['4k_uhd', 'blu_ray'])
  })

  it('keeps only real formats from an address, once each, in the form’s order', () => {
    expect(formatsFromParams(['dvd', 'nonsense', '4k_uhd', 'dvd'])).toEqual(['4k_uhd', 'dvd'])
    expect(formatsFromParams([])).toEqual([])
  })

  it('builds the address of Add a copy for the same film with the new format chosen', () => {
    expect(addCopyPath('m-1', ['4k_uhd'])).toBe('/collection/add?movie=m-1&format=4k_uhd')
    expect(addCopyPath('m-1')).toBe('/collection/add?movie=m-1')
  })
})
