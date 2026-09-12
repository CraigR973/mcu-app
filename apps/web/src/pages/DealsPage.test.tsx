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

  it('tells the admin who has to run the scrape when the feed is empty', () => {
    // §5.9's acceptance is a live run against real shops, which `group-start.md` puts in
    // the owner's hands — so an empty feed says so rather than implying nothing is on
    // offer.
    const html = markup(<DealsPage />, [])

    expect(html).toContain('No deals recorded yet')
    expect(html).toContain('manual step')
    expect(html).toContain('Retailers')
  })
})
