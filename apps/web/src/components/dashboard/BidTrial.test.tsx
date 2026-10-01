// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { BidTrial as Trial, TrialSummary } from '@/lib/api'

const { fetchTrialMock, startMock, auth } = vi.hoisted(() => ({
  fetchTrialMock: vi.fn(),
  startMock: vi.fn(),
  auth: { role: 'admin' },
}))
vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: 'p', displayName: 'Craig', role: auth.role } }),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchBidTrial: fetchTrialMock,
  startBidTrial: startMock,
}))

import { BidTrial } from './BidTrial'

function summary(formatCode: string | null, films: number): TrialSummary {
  return {
    formatCode,
    films,
    withBids: 1,
    withBidsEndingSoon: 0,
    auctionsCounted: 3,
    endingSoon: 1,
    compared: 1,
    bidToAskingPercent: 60,
    cut: 1,
    auctionOnlyPlaces: 8,
    askingSample: 27,
    storedSample: 25,
    askingLost: 0,
    stored: { total: '23.00', discs: 2 },
    asking: { total: '19.98', discs: 2 },
    bids: { total: '12.00', discs: 2 },
    blend: { total: '12.00', discs: 2, fromBids: 2, fromAsking: 0 },
  }
}

const FINISHED: Trial = {
  id: '3f2504e0-4f89-41d3-9a0c-0305e82c3410',
  status: 'finished',
  startedAt: '2026-10-01T09:00:00Z',
  finishedAt: '2026-10-01T09:02:10Z',
  budget: 750,
  calls: 2,
  failed: 1,
  lastError: 'Heat (4k_uhd): eBay search failed (HTTP 500)',
  sampleSize: 100,
  minSample: 3,
  endingWindowHours: 24,
  dailyShare: 750,
  currency: 'GBP',
  report: {
    sampled: 2,
    films: [
      {
        movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3401',
        title: 'Blade Runner 2049',
        formatCode: 'blu_ray',
        copies: 2,
        stored: { price: '11.50', sampleSize: 25 },
        results: { total: 304, returned: 200, buyItNow: 192, auctionOnly: 8 },
        asking: { price: '9.99', sampleSize: 27 },
        bids: { counted: 3, withoutBids: 2, rejected: 4, price: '6.00', endingSoon: 1 },
        error: null,
      },
      {
        movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3402',
        title: 'Heat',
        formatCode: '4k_uhd',
        copies: 1,
        stored: { price: '20.00', sampleSize: 9 },
        results: null,
        asking: null,
        bids: null,
        error: 'eBay search failed (HTTP 500)',
      },
    ],
    formats: [summary('4k_uhd', 0), summary('blu_ray', 1), summary('dvd', 0)],
    overall: summary(null, 1),
  },
}

function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <BidTrial />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  auth.role = 'admin'
  fetchTrialMock.mockReset().mockResolvedValue(null)
  startMock.mockReset()
})

afterEach(() => {
  cleanup()
})

describe('Try bid prices on Home — Batch V6', () => {
  it('is not shown to a viewer, who never asks for it', async () => {
    auth.role = 'viewer'
    renderIt()
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(screen.queryByRole('heading', { name: /Bid prices/ })).toBeNull()
    expect(fetchTrialMock).not.toHaveBeenCalled()
  })

  it('offers the trial before the first, saying what it spends and that it saves no prices', async () => {
    startMock.mockResolvedValue({ outcome: 'started', trial: { ...FINISHED, status: 'running', report: null }, sampled: 100, budgetLeft: 750 })
    renderIt()

    expect(await screen.findByRole('heading', { name: 'Bid prices: a trial' })).not.toBeNull()
    expect(screen.getByText(/Searches eBay once for each of up to 100 priced films/)).not.toBeNull()
    expect(screen.getByText(/It saves no prices\./)).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Try bid prices' }))
    await vi.waitFor(() => expect(startMock).toHaveBeenCalledTimes(1))
  })

  it('says why nothing started', async () => {
    startMock.mockResolvedValue({ outcome: 'budget_spent', trial: null, sampled: 100, budgetLeft: 0 })
    renderIt()

    fireEvent.click(await screen.findByRole('button', { name: 'Try bid prices' }))

    expect(await screen.findByText("Today's share of eBay lookups is used. Try again tomorrow.")).not.toBeNull()
  })

  it('shows the count while it runs, with no second button', async () => {
    fetchTrialMock.mockResolvedValue({
      ...FINISHED,
      status: 'running',
      finishedAt: null,
      failed: 0,
      report: { ...FINISHED.report, sampled: 100, films: FINISHED.report?.films.slice(0, 1) ?? [] },
    })
    renderIt()

    expect(await screen.findByText('Trying bid prices: 1 of 100 films looked up.')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Try bid prices' })).toBeNull()
  })

  it('reports by format: bids against asking, the totals on each basis, and the films', async () => {
    fetchTrialMock.mockResolvedValue(FINISHED)
    renderIt()

    expect(await screen.findByText("Tried 1 Oct 2026: 2 films looked up, 2 eBay lookups of the day's 750.")).not.toBeNull()
    expect(screen.getByText('eBay did not answer for 1 film; they are left out of every figure.')).not.toBeNull()

    const overall = within(screen.getByText('All formats · 1 film').closest('details') as HTMLElement)
    expect(overall.getByText('1 of 1 film had 3 or more auctions with bids.')).not.toBeNull()
    expect(overall.getByText('Bids were 60% of the asking price (the median of 1 film).')).not.toBeNull()
    const rows = overall.getAllByRole('row').map((row) => row.textContent)
    expect(rows).toEqual([
      'BasisTotalBehind it',
      'Asking, stored£232 discs',
      'Asking, today£202 discs',
      'Bids only£122 discs',
      'Blend£122 discs, 2 by bids',
    ])

    expect(screen.getByText('Blu-ray · 1 film')).not.toBeNull()
    expect(screen.getByText('4K UHD · 0 films')).not.toBeNull()
    const films = within(screen.getByText('Films with a bid price (1)').closest('details') as HTMLElement)
    expect(films.getByText(/bids £6\.00 from 3 · asking £9\.99 · stored £11\.50/)).not.toBeNull()
    // Starting another is still offered.
    expect(screen.getByRole('button', { name: 'Try bid prices' })).not.toBeNull()
  })

  it('says so when the trial cannot be started', async () => {
    startMock.mockRejectedValue(new Error('eBay is not configured in this deployment.'))
    renderIt()

    fireEvent.click(await screen.findByRole('button', { name: 'Try bid prices' }))

    expect((await screen.findByRole('alert')).textContent).toBe('eBay is not configured in this deployment.')
  })
})
