// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { EbayTarget, EbayTargets } from '@/lib/api'

const { targetsMock, createMock, changeMock, removeMock } = vi.hoisted(() => ({
  targetsMock: vi.fn(),
  createMock: vi.fn(),
  changeMock: vi.fn(),
  removeMock: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchEbayTargets: targetsMock,
  createListingTarget: createMock,
  changeTargetPrice: changeMock,
  removeTarget: removeMock,
}))

import PriceAlertsPage, { currentLine, validTarget } from './PriceAlertsPage'

const FILM = '00000000-0000-4000-8000-000000000041'

const LISTING: EbayTarget = {
  id: '00000000-0000-4000-8000-000000000042',
  kind: 'listing',
  status: 'watching',
  title: 'THE BRAZEN BULL (NICTOPHOBIA) - Dvd  -',
  movieId: null,
  formatCode: null,
  targetPrice: '5.00',
  currency: 'GBP',
  url: 'https://www.ebay.co.uk/itm/168722516953',
  imageUrl: null,
  isAuction: false,
  currentPrice: '6.99',
  currentPostage: '0.00',
  currentUrl: 'https://www.ebay.co.uk/itm/168722516953',
  endsAt: '2026-10-03T09:06:39Z',
  lastCheckedAt: '2026-09-26T09:20:00Z',
  metAt: null,
  lastError: null,
  createdAt: '2026-09-26T09:00:00Z',
}

const SEARCH: EbayTarget = {
  ...LISTING,
  id: '00000000-0000-4000-8000-000000000043',
  kind: 'search',
  status: 'watching',
  title: 'Star Wars: The Last Jedi',
  movieId: FILM,
  formatCode: '4k_uhd',
  targetPrice: '5.00',
  url: null,
  currentPrice: '3.84',
  currentPostage: '0.91',
  currentUrl: 'https://www.ebay.co.uk/itm/298708357566',
  endsAt: null,
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PriceAlertsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  targetsMock.mockReset()
  createMock.mockReset()
  changeMock.mockReset()
  removeMock.mockReset()
})
afterEach(cleanup)

describe('PriceAlertsPage — Batch T8a', () => {
  it('says nothing is checked until the schedule is on', async () => {
    targetsMock.mockResolvedValue({ items: [LISTING], lastRun: null } satisfies EbayTargets)
    renderPage()
    expect(await screen.findByText(/It is not on yet, so nothing is being checked/)).toBeTruthy()
  })

  it('shows each alert with its price, what eBay has now, and a link to it', async () => {
    targetsMock.mockResolvedValue({
      items: [SEARCH, LISTING],
      lastRun: {
        status: 'finished',
        startedAt: '2026-09-26T09:20:00Z',
        finishedAt: '2026-09-26T09:21:00Z',
        targetsChecked: 2,
        dealsFound: 0,
      },
    } satisfies EbayTargets)
    renderPage()
    const search = (await screen.findByText('Any 4K UHD of Star Wars: The Last Jedi')).closest('li')
    expect(search).toBeTruthy()
    const card = within(search as HTMLElement)
    expect(card.getByText('Cheapest UK copy: £3.84 + £0.91 postage.')).toBeTruthy()
    expect(card.getByRole('link', { name: /Open on eBay/ }).getAttribute('href')).toBe(
      'https://www.ebay.co.uk/itm/298708357566',
    )
    expect(card.getByRole('link', { name: /Star Wars/ }).getAttribute('href')).toBe(`/movies/${FILM}`)
    expect(screen.getByText('Buy It Now: £6.99, free postage.')).toBeTruthy()
    expect(screen.getByText(/Last check 26 Sep 2026, 10:20/)).toBeTruthy()
  })

  it('watches a listing from its address and the price typed', async () => {
    targetsMock.mockResolvedValue({ items: [], lastRun: null } satisfies EbayTargets)
    createMock.mockResolvedValue(LISTING)
    renderPage()
    const button = await screen.findByRole('button', { name: /Watch this listing/ })
    fireEvent.change(screen.getByPlaceholderText('https://www.ebay.co.uk/itm/…'), {
      target: { value: '  https://www.ebay.co.uk/itm/168722516953  ' },
    })
    fireEvent.change(screen.getByPlaceholderText('8.00'), { target: { value: '5.x' } })
    expect((button as HTMLButtonElement).disabled).toBe(true)
    fireEvent.change(screen.getByPlaceholderText('8.00'), { target: { value: '5.00' } })
    fireEvent.click(button)
    await waitFor(() =>
      expect(createMock).toHaveBeenCalledWith('https://www.ebay.co.uk/itm/168722516953', '5.00'),
    )
    expect(await screen.findByText(/Watching THE BRAZEN BULL/)).toBeTruthy()
  })

  it('removes an alert', async () => {
    targetsMock.mockResolvedValue({ items: [LISTING], lastRun: null } satisfies EbayTargets)
    removeMock.mockResolvedValue(undefined)
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Remove/ }))
    await waitFor(() => expect(removeMock).toHaveBeenCalledWith(LISTING.id))
  })
})

describe('the words for what eBay has now', () => {
  it('names an auction’s bid and a listing never checked', () => {
    expect(currentLine({ ...LISTING, isAuction: true, currentPrice: '4.99' })).toBe('Bidding at £4.99.')
    expect(currentLine({ ...LISTING, lastCheckedAt: null })).toBe('Not checked yet.')
    expect(currentLine({ ...SEARCH, currentPrice: null })).toBe('No UK Buy It Now copy found at the last check.')
  })

  it('accepts pounds and pence only', () => {
    expect(validTarget('8')).toBe(true)
    expect(validTarget('8.5')).toBe(true)
    expect(validTarget('8.999')).toBe(false)
    expect(validTarget('0')).toBe(false)
    expect(validTarget('£8')).toBe(false)
  })
})
