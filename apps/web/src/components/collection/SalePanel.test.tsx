import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { SalePanel } from './SalePanel'
import { UpgradePrompt } from './UpgradePrompt'
import type { CollectionCopy } from '@/lib/api'

function markup(node: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return renderToStaticMarkup(<QueryClientProvider client={client}>{node}</QueryClientProvider>)
}

const bluRay: CollectionCopy = {
  id: '3f2504e0-4f89-11d3-9a0c-0305e82c3303',
  formats: ['blu_ray'],
  location: 'Back 6th shelf',
  section: 'Back',
  shelf: '6th',
  subCategory: null,
  notes: null,
  purchasePrice: null,
  purchaseSource: null,
  purchaseDate: null,
  condition: 'good',
  hasPlaybackIssues: false,
  playbackNotes: null,
  videoSpecs: null,
  audioSpecs: null,
  specialFeatures: null,
  regionCode: null,
  releaseLabel: null,
  listingStatus: 'in_collection',
  ebayListingUrl: null,
  listingPrice: null,
  updatedAt: '2026-09-12T09:00:00Z',
  valuation: null,
}

const fourK: CollectionCopy = { ...bluRay, id: 'a-4k-disc', formats: ['4k_uhd'] }

describe('SalePanel', () => {
  it('offers to list a disc that is on the shelf', () => {
    const html = markup(<SalePanel copy={bluRay} movieId="m1" />)

    expect(html).toContain('List for sale')
    expect(html).toContain('Asking price')
    // Nothing about selling yet — the disc has not been listed.
    expect(html).not.toContain('Mark as sold')
  })

  it('pre-fills the asking price from §4.1 rather than asking for one', () => {
    // "Admin adjusts or accepts" — the number arrives already in the box. Making someone
    // type a price before anything can happen is the tap §4.2's ≤3 budget cannot spare.
    const html = markup(<SalePanel copy={bluRay} movieId="m1" suggestedPrice="9.99" />)

    expect(html).toContain('value="9.99"')
  })

  it('keeps a listed disc visible and offers the sale', () => {
    // A disc advertised is still a disc in the house. Hiding it here would make listing
    // it indistinguishable from losing it.
    const listed: CollectionCopy = {
      ...bluRay,
      listingStatus: 'listed_for_sale',
      listingPrice: '9.99',
    }
    const html = markup(<SalePanel copy={listed} movieId="m1" />)

    expect(html).toContain('Listed for sale')
    expect(html).toContain('£9.99')
    expect(html).toContain('Mark as sold')
    expect(html).toContain('Keep it after all')
  })

  it('says a sold disc was not deleted', () => {
    // §4.4: "remains in audit/trash". The row is kept precisely so the 90-day trash purge
    // cannot destroy the record of what it fetched, and the panel says so rather than
    // leaving someone to wonder where it went.
    const sold: CollectionCopy = { ...bluRay, listingStatus: 'sold', listingPrice: '12.50' }
    const html = markup(<SalePanel copy={sold} movieId="m1" />)

    expect(html).toContain('Sold')
    expect(html).toContain('for £12.50')
    expect(html).toContain('still in the audit log')
    expect(html).not.toContain('List for sale')
  })
})

describe('UpgradePrompt', () => {
  it('names the superseded disc and offers one tap to list it', () => {
    // §4.2's acceptance is "≤ 3 taps". Tap one is "This is an upgrade" on the duplicate
    // prompt, which is also the save; tap two is this button.
    const html = markup(
      <UpgradePrompt
        movieId="m1"
        filmTitle="Blade Runner 2049"
        copies={[bluRay, fourK]}
        onDismiss={() => {}}
      />,
    )

    expect(html).toContain('You&#x27;ve upgraded to 4K UHD')
    expect(html).toContain('List for sale')
    expect(html).toContain('Back 6th shelf')
  })

  it('renders nothing when no disc was superseded', () => {
    // Adding a second copy of the same format is not an upgrade, and a prompt offering to
    // sell the disc you just matched would be actively wrong.
    const html = markup(
      <UpgradePrompt
        movieId="m1"
        filmTitle="Blade Runner 2049"
        copies={[bluRay, { ...bluRay, id: 'another-blu-ray' }]}
        onDismiss={() => {}}
      />,
    )

    expect(html).toBe('')
  })

  it('does not offer to sell a disc that is already listed', () => {
    const html = markup(
      <UpgradePrompt
        movieId="m1"
        filmTitle="Blade Runner 2049"
        copies={[{ ...bluRay, listingStatus: 'listed_for_sale' }, fourK]}
        onDismiss={() => {}}
      />,
    )

    expect(html).toBe('')
  })
})
