import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { Deal } from '@/lib/api'

vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: 'p1', displayName: 'Craig', role: 'admin' } }),
}))

const { default: DealsPage } = await import('./DealsPage')

function markup(node: React.ReactElement, deals: Deal[] = []) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  // Seed the cache so the page renders its loaded state without a network round trip —
  // the same approach the other page tests take.
  client.setQueryData(['deals', {}], {
    items: deals,
    total: deals.length,
    retailers: [...new Set(deals.map((deal) => deal.retailer))],
    genres: [...new Set(deals.flatMap((deal) => deal.genres))],
  })
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>,
  )
}

const deal: Deal = {
  id: '3f2504e0-4f89-11d3-9a0c-0305e82c3303',
  retailer: 'Zavvi',
  title: 'Cross Of Iron',
  url: 'https://www.zavvi.com/p/blu-ray/cross-of-iron/10369739/',
  imageUrl: null,
  formatCode: 'blu_ray',
  price: '12.99',
  wasPrice: '24.99',
  currency: 'GBP',
  discountPercent: 48,
  movieId: '3f2504e0-4f89-11d3-9a0c-0305e82c3304',
  tmdbId: 11234,
  posterPath: '/cross.jpg',
  genres: ['War'],
  firstSeenAt: '2026-09-12T09:00:00Z',
  lastSeenAt: '2026-09-12T09:00:00Z',
  usualSources: null,
  soldListingsUrl: null,
  condition: null,
  usualListings: null,
}

/** An eBay find (V8, X1): eBay's figure lowered to Zavvi's cheaper price, a used copy. */
const ebayFind: Deal = {
  ...deal,
  id: '3f2504e0-4f89-11d3-9a0c-0305e82c3305',
  retailer: 'eBay',
  title: 'Star Wars The Last Jedi 4K UHD + Blu-ray',
  url: 'https://www.ebay.co.uk/itm/298708357566',
  formatCode: '4k_uhd',
  price: '4.75',
  wasPrice: '14.00',
  discountPercent: 66,
  lastSeenAt: '2026-09-30T19:14:57Z',
  condition: 'Very good',
  usualListings: 12,
  usualSources: [
    { source: 'eBay', price: '16.00' },
    { source: 'Zavvi', price: '14.00' },
  ],
  soldListingsUrl:
    'https://www.ebay.co.uk/sch/i.html?_nkw=Star+Wars%3A+The+Last+Jedi+4K&_sacat=617&LH_Sold=1&LH_Complete=1',
}

describe('DealsPage', () => {
  it('shows the discount, both prices and where to buy it', () => {
    const html = markup(<DealsPage />, [deal])

    expect(html).toContain('−48%')
    expect(html).toContain('£12.99')
    expect(html).toContain('£24.99')
    expect(html).toContain('View at Zavvi')
    expect(html).toContain('https://www.zavvi.com/p/blu-ray/cross-of-iron/10369739/')
  })

  it('opens the retailer in a new tab without handing it a window reference', () => {
    // `noopener` is not optional on a `_blank` link to somebody else's site.
    const html = markup(<DealsPage />, [deal])

    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('offers §5.10’s four filters, and only values the feed actually has', () => {
    const html = markup(<DealsPage />, [deal])

    expect(html).toContain('25% or more') // discount
    expect(html).toContain('Blu-ray') // format
    expect(html).toContain('Zavvi') // retailer
    expect(html).toContain('War') // genre
    // A genre nothing in the feed carries is not offered, so no filter can produce a
    // guaranteed blank.
    expect(html).not.toContain('Western')
  })

  it('says an unmatched deal is unmatched rather than hiding it', () => {
    // A deal the matcher could not place is the evidence that the matcher needs work.
    // Hiding it would make a broken matcher look like a quiet sale page.
    const html = markup(<DealsPage />, [{ ...deal, movieId: null, posterPath: null }])

    expect(html).toContain('Not matched to a film in the archive')
    expect(html).toContain('Cross Of Iron')
  })

  it('says what an eBay find\'s "usually" is made of, and links to what it sold for', () => {
    const html = markup(<DealsPage />, [ebayFind])

    expect(html).toContain('with postage · usually £14.00 (asking prices, 12 listings)')
    expect(html).toContain('eBay £16.00 before postage · Zavvi £14.00')
    expect(html).toContain('Sold on eBay')
    // React escapes the ampersands in an attribute.
    expect(html).toContain(ebayFind.soldListingsUrl?.replaceAll('&', '&amp;'))
  })

  it('names the listing\'s condition and when every deal\'s price was last seen', () => {
    // Batch X1: "Seen 30 Sep" on every card, a shop's and an eBay find's alike.
    const html = markup(<DealsPage />, [ebayFind, deal])

    expect(html).toContain('eBay · Very good · Seen 30 Sep')
    expect(html).toContain('Zavvi · Seen 12 Sep')
    expect(html).toContain('Star Wars The Last Jedi 4K UHD + Blu-ray')
  })

  it('gives a shop\'s own deal no sold-listings link and no parts', () => {
    const html = markup(<DealsPage />, [deal])

    expect(html).not.toContain('Sold on eBay')
    expect(html).not.toContain('before postage')
  })

  it('says when each source last answered when nothing is on offer — Batch X2', () => {
    // Before X2 it said the sale pages had not been scraped, while the eBay scan, the main
    // source since T8a, was blind; and Deals left the menu.
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['deals', {}], {
      items: [],
      total: 0,
      retailers: [],
      genres: [],
      sources: [
        { name: 'eBay', lastAnsweredAt: '2026-10-12T20:23:00Z' },
        { name: 'Zavvi', lastAnsweredAt: '2026-09-30T19:14:00Z' },
      ],
    })
    const html = renderToStaticMarkup(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <DealsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(html).toContain('Nothing on offer right now')
    expect(html).toContain(
      'eBay was last read 12 Oct; Zavvi&#x27;s sale page last gave a deal 30 Sep.',
    )
    expect(html).toContain('checked from Retailers')
  })

})
