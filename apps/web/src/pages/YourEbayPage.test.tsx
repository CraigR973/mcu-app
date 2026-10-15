// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { EbaySelling, EbayWatching, MovieListItem, WantedItem } from '@mcu/shared'

const api = vi.hoisted(() => ({
  fetchEbayWatching: vi.fn(),
  fetchEbaySelling: vi.fn(),
  createListingTarget: vi.fn(),
  createSearchTarget: vi.fn(),
  fetchSearch: vi.fn(),
  fetchWanted: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))

import { ApiError } from '@/lib/api'

import YourEbayPage from './YourEbayPage'

const WATCHING: EbayWatching = {
  items: [
    {
      itemId: '226100000010',
      title: 'Dog Soldiers 4K UHD Second Sight',
      url: 'https://www.ebay.co.uk/itm/226100000010',
      price: '24.99',
      currency: 'GBP',
      postage: '0.00',
      isAuction: false,
      bidCount: null,
      endsAt: '2026-10-10T20:00:00Z',
    },
  ],
  savedSearches: [{ name: 'dog soldiers 4k', keywords: 'dog soldiers 4k', url: null }],
  totalItems: 1,
  fetchedAt: '2026-10-04T09:00:00Z',
}

const SELLING: EbaySelling = {
  active: [
    {
      itemId: '226100000011',
      title: 'Heat Blu-ray',
      url: 'https://www.ebay.co.uk/itm/226100000011',
      price: '8.00',
      currency: 'GBP',
      postage: null,
      isAuction: true,
      bidCount: 2,
      endsAt: null,
    },
  ],
  sold: [
    {
      itemId: '226100000012',
      title: 'Alien DVD',
      url: 'https://www.ebay.co.uk/itm/226100000012',
      price: '3.50',
      currency: 'GBP',
      soldAt: '2026-09-28T09:12:44Z',
    },
  ],
  totalActive: 1,
  totalSold: 1,
  fetchedAt: '2026-10-04T09:00:00Z',
}

const DOG_SOLDIERS = '3f2504e0-4f89-41d3-9a0c-0305e82c3401'

function want(movieId: string, movieTitle: string, year: number, preferredFormat: string | null): WantedItem {
  return {
    id: `${movieId.slice(0, -4)}9999`,
    movieId,
    movieTitle,
    year,
    posterPath: null,
    preferredFormat,
    preferredEdition: null,
    maxPrice: null,
    currency: 'GBP',
    isActive: true,
    notes: null,
    ownedAlready: false,
    addedAt: '2026-09-30T20:00:00Z',
    reviews: [],
  }
}

function owned(id: string, title: string, year: number): MovieListItem {
  return {
    id,
    title,
    originalTitle: title,
    year,
    posterPath: null,
    backdropPath: null,
    tmdbRating: 6.7,
    runtimeMinutes: 105,
    bestFormatOwned: 'dvd',
    bestHdrOwned: null,
    bestAudioOwned: null,
    identified: true,
    setAsideAs: null,
    copyCount: 1,
    locations: [],
    watched: false,
    lastWatchedAt: null,
    editions: [],
  }
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <YourEbayPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Your eBay — Batch T8b', () => {
  it('shows what you watch, with a price alert one form away', async () => {
    api.fetchEbayWatching.mockResolvedValue(WATCHING)
    api.createListingTarget.mockResolvedValue({})
    renderPage()

    const listing = await screen.findByRole('link', { name: 'Dog Soldiers 4K UHD Second Sight' })
    expect(listing.getAttribute('href')).toBe('https://www.ebay.co.uk/itm/226100000010')
    expect(screen.getByText(/£24\.99 · free postage/)).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Alert me' }))
    fireEvent.change(screen.getByLabelText(/Alert me when Dog Soldiers/), { target: { value: '20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(api.createListingTarget).toHaveBeenCalledWith('https://www.ebay.co.uk/itm/226100000010', '20'),
    )
    expect(await screen.findByText('Alert set: under £20.')).not.toBeNull()
  })

  it('finds a saved search\'s film on Wanted, taking the format from its words', async () => {
    api.fetchEbayWatching.mockResolvedValue(WATCHING)
    api.fetchWanted.mockResolvedValue({
      items: [want(DOG_SOLDIERS, 'Dog Soldiers', 2002, 'blu_ray'), want('3f2504e0-4f89-41d3-9a0c-0305e82c3404', 'Heat', 1995, null)],
      total: 2,
      activeCount: 2,
    })
    api.fetchSearch.mockResolvedValue({ query: 'dog soldiers', total: 0, items: [] })
    api.createSearchTarget.mockResolvedValue({})
    renderPage()

    // The search is "dog soldiers 4k": the catalogue is asked for the film's words alone.
    fireEvent.click(await screen.findByRole('button', { name: 'Make an alert' }))
    const choice = await screen.findByRole('radio', { name: /Dog Soldiers \(2002\) · on Wanted/ })
    expect(screen.queryByRole('radio', { name: /Heat/ })).toBeNull()
    expect(api.fetchSearch).toHaveBeenCalledWith('dog soldiers', 8)
    fireEvent.click(choice)
    // "4k" chose the format, over the want's own Blu-ray.
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('4k_uhd')
    fireEvent.change(screen.getByLabelText(/Alert me when Dog Soldiers is under/), { target: { value: '18.50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => expect(api.createSearchTarget).toHaveBeenCalledWith(DOG_SOLDIERS, '4k_uhd', '18.50'))
    expect(await screen.findByText(/Alert set: Dog Soldiers, 4K UHD, under £\s*18\.50\./)).not.toBeNull()
  })

  it('finds an owned film once the words are edited, at Blu-ray until another format is chosen', async () => {
    api.fetchEbayWatching.mockResolvedValue({
      ...WATCHING,
      savedSearches: [{ name: 'Heat steelbook', keywords: 'heat steelbook', url: null }],
    })
    api.fetchWanted.mockResolvedValue({ items: [], total: 0, activeCount: 0 })
    api.fetchSearch.mockImplementation((query: string) =>
      Promise.resolve(
        query === 'heat'
          ? { query, total: 1, items: [owned('3f2504e0-4f89-41d3-9a0c-0305e82c3404', 'Heat', 1995)] }
          : { query, total: 0, items: [] },
      ),
    )
    api.createSearchTarget.mockResolvedValue({})
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Make an alert' }))
    // "steelbook" stays in the words, and the catalogue matches every word, so it is edited out.
    expect(await screen.findByText(/No film on Wanted or in the collection matches/)).not.toBeNull()
    expect(api.fetchSearch).toHaveBeenCalledWith('heat steelbook', 8)
    fireEvent.change(screen.getByLabelText('Which film is this search for?'), { target: { value: 'heat' } })
    fireEvent.click(screen.getByRole('button', { name: 'Find' }))
    fireEvent.click(await screen.findByRole('radio', { name: /Heat \(1995\)/ }))
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('blu_ray')
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'dvd' } })
    fireEvent.change(screen.getByLabelText(/Alert me when Heat is under/), { target: { value: '5' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() =>
      expect(api.createSearchTarget).toHaveBeenCalledWith('3f2504e0-4f89-41d3-9a0c-0305e82c3404', 'dvd', '5'),
    )
  })

  it("takes a want's own format when the search's words name none", async () => {
    api.fetchEbayWatching.mockResolvedValue({
      ...WATCHING,
      savedSearches: [{ name: 'heat', keywords: null, url: null }],
    })
    api.fetchWanted.mockResolvedValue({
      items: [want('3f2504e0-4f89-41d3-9a0c-0305e82c3404', 'Heat', 1995, '4k_uhd')],
      total: 1,
      activeCount: 1,
    })
    api.fetchSearch.mockResolvedValue({ query: 'heat', total: 0, items: [] })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Make an alert' }))
    fireEvent.click(await screen.findByRole('radio', { name: /Heat \(1995\) · on Wanted/ }))
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('4k_uhd')
  })

  it('shows what you sell and what sold, on its own tab', async () => {
    api.fetchEbayWatching.mockResolvedValue(WATCHING)
    api.fetchEbaySelling.mockResolvedValue(SELLING)
    renderPage()

    fireEvent.click(await screen.findByRole('tab', { name: 'Selling' }))

    const forSale = within(await screen.findByRole('region', { name: 'For sale' }))
    expect(forSale.getByText('Heat Blu-ray')).not.toBeNull()
    expect(forSale.getByText('£8.00 · 2 bids')).not.toBeNull()
    const sold = within(screen.getByRole('region', { name: 'Sold in the last 60 days' }))
    expect(sold.getByText('Alien DVD')).not.toBeNull()
  })

  it('points to Settings when eBay is not connected', async () => {
    api.fetchEbayWatching.mockRejectedValue(
      new ApiError('Connect eBay in Settings to see your eBay lists here.', 409),
    )
    renderPage()

    expect(await screen.findByText('eBay is not connected')).not.toBeNull()
    expect(screen.getByText('Connect eBay in Settings to see your eBay lists here.')).not.toBeNull()
    expect(screen.getByRole('link', { name: 'Go to Settings' }).getAttribute('href')).toBe('/settings?tab=ebay')
  })

  it('says what eBay said when it refuses, and does not send the person to Settings', async () => {
    api.fetchEbayWatching.mockRejectedValue(
      new ApiError('eBay refused GetMyeBayBuying: IAF token supplied is invalid. even with a fresh sign-in', 502),
    )
    renderPage()

    expect(await screen.findByText('Your watch list could not be read')).not.toBeNull()
    expect(screen.getByText(/even with a fresh sign-in/)).not.toBeNull()
    expect(screen.queryByRole('link', { name: 'Go to Settings' })).toBeNull()
  })
})
