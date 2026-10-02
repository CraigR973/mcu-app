import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { StoredValue } from './StoredValue'
import type { CopyValuation } from '@/lib/api'

/**
 * Batch V8: beside the asking prices a disc is valued at, a link to what it actually sold
 * for on eBay. The app cannot read sold listings; eBay asks the person to sign in.
 */
const SOLD =
  'https://www.ebay.co.uk/sch/i.html?_nkw=Heat+4K&_sacat=617&LH_Sold=1&LH_Complete=1'

const priced: CopyValuation = {
  formatCode: '4k_uhd',
  status: 'priced',
  price: '19.50',
  currency: 'GBP',
  sampleSize: 12,
  conditionLabel: 'New',
  checkedAt: '2026-09-26T08:00:00Z',
  basis: 'current asking prices',
  minSample: 3,
  soldListingsUrl: SOLD,
}

describe('StoredValue', () => {
  it('links a priced disc to its sold listings, in a new tab', () => {
    const html = renderToStaticMarkup(<StoredValue valuation={priced} />)

    expect(html).toContain('£19.50')
    expect(html).toContain('Sold listings on eBay')
    expect(html).toContain(`href="${SOLD.replaceAll('&', '&amp;')}"`)
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('links an unpriced disc too: sold listings may exist where asking prices are few', () => {
    const html = renderToStaticMarkup(
      <StoredValue valuation={{ ...priced, status: 'not_priced', price: null, sampleSize: 2 }} />,
    )

    expect(html).toContain('Not priced when checked')
    expect(html).toContain('Sold listings on eBay')
  })

  it('shows no link when the API sends none', () => {
    const html = renderToStaticMarkup(<StoredValue valuation={{ ...priced, soldListingsUrl: null }} />)

    expect(html).not.toContain('Sold listings on eBay')
  })
})
