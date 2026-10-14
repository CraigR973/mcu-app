// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { CollectionValue as Value } from '@/lib/api'

const { fetchValueMock, startMock, auth } = vi.hoisted(() => ({
  fetchValueMock: vi.fn(),
  startMock: vi.fn(),
  auth: { role: 'viewer' },
}))
vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: 'p', displayName: 'Craig', role: auth.role } }),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchCollectionValue: fetchValueMock,
  startValuationRun: startMock,
}))

import { CollectionValue } from './CollectionValue'

const VALUED: Value = {
  total: '12345.60',
  currency: 'GBP',
  basis: 'current asking prices',
  valuedAs: 'as used copies',
  discs: 1457,
  pricedDiscs: 1302,
  notPricedDiscs: 103,
  uncheckedDiscs: 52,
  checkedFrom: '2026-09-23T03:00:00Z',
  checkedTo: '2026-09-24T03:10:00Z',
  due: 52,
  budgetLeft: 750,
  dailyShare: 750,
  minSample: 3,
  run: null,
}

const NOT_YET: Value = {
  ...VALUED,
  total: null,
  pricedDiscs: 0,
  notPricedDiscs: 0,
  uncheckedDiscs: 1457,
  checkedFrom: null,
  checkedTo: null,
  due: 1454,
}

function renderIt() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const view = render(
    <QueryClientProvider client={client}>
      <CollectionValue />
    </QueryClientProvider>,
  )
  return view
}

beforeEach(() => {
  auth.role = 'viewer'
  fetchValueMock.mockReset().mockResolvedValue(VALUED)
  startMock.mockReset()
})

afterEach(() => {
  cleanup()
})

describe('CollectionValue — Batch T6', () => {
  it('gives the total at asking prices, how many discs it rests on, and when', async () => {
    renderIt()

    expect(await screen.findByText(/£12,346/)).not.toBeNull()
    expect(screen.getByText('as used copies, at current asking prices on eBay')).not.toBeNull()
    expect(screen.getByText('1,302 of 1,457 discs priced · checked 23–24 Sep 2026')).not.toBeNull()
    expect(screen.getByText(/103 had fewer than 3 used and 3 new matching eBay listings, so they are not priced rather than guessed/)).not.toBeNull()
    expect(screen.getByText(/52 not valued as used copies yet; the next run does them first/)).not.toBeNull()
    expect(screen.getByText(/Each disc is valued as a used copy/)).not.toBeNull()
    expect(screen.getByText(/usually run above what discs actually sell for/)).not.toBeNull()
  })

  it('offers a viewer no button, because a run spends the shared eBay allowance', async () => {
    renderIt()
    await screen.findByText(/£12,346/)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('says nothing to a viewer before there is a total', async () => {
    fetchValueMock.mockResolvedValue(NOT_YET)
    const { container } = renderIt()
    await vi.waitFor(() => expect(fetchValueMock).toHaveBeenCalled())
    expect(container.textContent).toBe('')
  })

  it('lets an admin start the first valuation, and says what it will cost', async () => {
    auth.role = 'admin'
    fetchValueMock.mockResolvedValue(NOT_YET)
    startMock.mockResolvedValue({ outcome: 'budget_spent', run: null, due: 1454, budgetLeft: 0 })
    renderIt()

    expect(await screen.findByText(/Not valued yet/)).not.toBeNull()
    expect(screen.getByText(/about 750 lookups a day/)).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Value the collection/ }))

    expect(await screen.findByText(/Today's share of eBay lookups is used. It carries on tomorrow./)).not.toBeNull()
    expect(startMock).toHaveBeenCalledTimes(1)
  })

  it('shows progress while a run is pricing, instead of the button', async () => {
    auth.role = 'admin'
    fetchValueMock.mockResolvedValue({
      ...VALUED,
      due: 1142,
      run: {
        id: '00000000-0000-4000-8000-000000000001',
        trigger: 'admin',
        status: 'running',
        startedAt: '2026-09-24T09:00:00Z',
        finishedAt: null,
        budget: 750,
        calls: 312,
        priced: 280,
        notPriced: 30,
        failed: 2,
        remaining: null,
        lastError: null,
      },
    })
    renderIt()

    expect(await screen.findByRole('status')).not.toBeNull()
    expect(screen.getByText(/Pricing now: 312 checked, 1,142 to go./)).not.toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('tells an admin when there is nothing to update', async () => {
    auth.role = 'admin'
    fetchValueMock.mockResolvedValue({ ...VALUED, due: 0, uncheckedDiscs: 0 })
    renderIt()

    expect(await screen.findByText('Every price is less than 30 days old.')).not.toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })
})
