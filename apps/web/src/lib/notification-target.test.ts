import { describe, expect, it } from 'vitest'

import { opensInApp } from './notification-target'

const ORIGIN = 'https://mcu.example.app'

describe('opensInApp — Batch T8a', () => {
  it('keeps the app’s own pages in the app', () => {
    expect(opensInApp('/movie-night/abc', ORIGIN)).toBe(true)
    expect(opensInApp(`${ORIGIN}/wanted`, ORIGIN)).toBe(true)
  })

  it('sends an eBay listing to a window of its own', () => {
    expect(opensInApp('https://www.ebay.co.uk/itm/298708357566', ORIGIN)).toBe(false)
  })

  it('treats an address that does not parse as the app’s', () => {
    expect(opensInApp('http://[not a host', ORIGIN)).toBe(true)
  })
})
