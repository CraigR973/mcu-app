import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { Estimate, ValuePanel } from './ValuePanel'
import type { EbayPriceEstimate } from '@/lib/api'

/**
 * The three things §4.1's surface must never get wrong.
 *
 * Rendered statically, like `DuplicatePrompt.test.tsx`: nothing here needs a click, and
 * the panel deliberately fetches nothing on mount — an estimate spends a unit of a finite
 * daily quota and this panel sits inside every copy on a film's page.
 */
function markup(node: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>{node}</QueryClientProvider>,
  )
}

const estimate: EbayPriceEstimate = {
  filmTitle: 'Blade Runner 2049',
  formatCode: 'blu_ray',
  marketplaceId: 'EBAY_GB',
  considered: 200,
  matched: 117,
  segments: [
    {
      formatCode: 'blu_ray',
      edition: 'standard',
      conditionId: '1000',
      conditionLabel: 'New',
      sampleSize: 29,
      median: '9.99',
      low: '4.16',
      high: '45.99',
      currency: 'GBP',
    },
    {
      formatCode: '4k_uhd',
      edition: 'collector',
      conditionId: '1000',
      conditionLabel: 'New',
      sampleSize: 27,
      median: '149.99',
      low: '42.29',
      high: '924.70',
      currency: 'GBP',
    },
  ],
  headline: null,
  rejected: { "ships from JP, not GB": 7 },
  unusable: 0,
  basis: 'current asking prices',
}

const withHeadline: EbayPriceEstimate = { ...estimate, headline: estimate.segments[0] }

describe('ValuePanel', () => {
  it('fetches nothing until it is asked to', () => {
    // An estimate costs a unit of a 5,000-a-day production quota, and this panel renders
    // once per owned copy. Loading on mount spends one per copy per page view, for a
    // number nobody asked for.
    const html = markup(<ValuePanel filmTitle="Blade Runner 2049" formatCode="blu_ray" />)

    expect(html).toContain('What is it worth?')
    expect(html).not.toContain('current asking prices')
    expect(html).not.toContain('median of')
  })

  it('offers the listing link without needing a price first', () => {
    // Phase 4.3's whole remaining path. The link is the feature; the price is an aid to
    // it, so an eBay outage must not stop somebody listing a disc.
    const html = markup(<ValuePanel filmTitle="Jaws" year={1975} formatCode="4k_uhd" />)

    expect(html).toContain('List on eBay')
  })
})

describe('the estimate, once asked for', () => {
  it('never shows a price without saying it is an asking price', () => {
    // Sold comps are unobtainable (`DECISIONS.md` #16, re-confirmed by #126). A surface
    // implying "this is what it sells for" would state something nobody can know. The
    // words come from the server's `basis`, so they cannot drift from what the API means.
    const html = renderToStaticMarkup(<Estimate estimate={withHeadline} />)

    expect(html).toContain('current asking prices')
    expect(html).toContain('£9.99')
  })

  it('never shows a price without its sample size', () => {
    // `DECISIONS.md` #129: £30.45 and £12.21 look equally reasonable on a card. Only
    // "median of 29 listings" tells them apart.
    const html = renderToStaticMarkup(<Estimate estimate={withHeadline} />)

    expect(html).toContain('median of 29 listings')
    expect(html).toContain('117 of 200 listings matched this disc')
  })

  it('shows the collector segment as a comparison, never as the headline', () => {
    // #129's 149% lives exactly here: the £149.99 4K steelbook is a real listing and a
    // real market, and it is not what this Blu-ray is worth.
    const html = renderToStaticMarkup(<Estimate estimate={withHeadline} />)

    const headlinePosition = html.indexOf('£9.99')
    const collectorPosition = html.indexOf('£149.99')
    expect(headlinePosition).toBeGreaterThan(-1)
    expect(collectorPosition).toBeGreaterThan(headlinePosition)
    expect(html).toContain('collector')
  })

  it('says nothing matched rather than showing a blank card', () => {
    // A search that matched nothing is an answer — a rare disc, or a title eBay spells
    // differently — and a blank would read as a bug.
    const html = renderToStaticMarkup(<Estimate estimate={estimate} />)

    expect(html).toContain('Nothing on eBay UK matched this disc')
    expect(html).toContain('200 listings were')
  })
})
