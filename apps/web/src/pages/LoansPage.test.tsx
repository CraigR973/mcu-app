// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CollectionCopy, Loan } from '@mcu/shared'

const MARK = '3f2504e0-4f89-41d3-9a0c-0305e82c3001'
vi.mock('@/context/auth', () => ({
  useAuth: () => ({
    profile: { id: MARK, displayName: 'Mark', role: 'viewer', hasPin: true, onboardingCompleted: true },
  }),
}))

const api = vi.hoisted(() => ({
  fetchLoans: vi.fn(),
  lendDisc: vi.fn(),
  returnLoan: vi.fn(),
  lookupBarcode: vi.fn(),
  confirmBarcode: vi.fn(),
  fetchCopies: vi.fn(),
  fetchSearch: vi.fn(),
  fetchSearchBeyond: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))

import LoansPage from './LoansPage'

const HEAT = '3f2504e0-4f89-41d3-9a0c-0305e82c3301'
const DISC = '3f2504e0-4f89-41d3-9a0c-0305e82c3101'
const CODE = '5051892123450'

const LOAN: Loan = {
  id: '3f2504e0-4f89-41d3-9a0c-0305e82c3201',
  collectionItemId: DISC,
  movieId: HEAT,
  movieTitle: 'Heat',
  posterPath: null,
  formats: ['bluray'],
  locationLabel: 'Front · 3',
  borrowerName: 'Dave',
  borrowerProfileId: null,
  lentDate: '2026-10-01',
  dueDate: null,
  returnedDate: null,
  isOverdue: false,
  daysUntilDue: null,
  notes: null,
}

function list(items: Loan[]) {
  return { items, total: items.length, openCount: items.length, overdueCount: 0 }
}

function renderLoans() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/loans']}>
        <LoansPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.fetchLoans.mockResolvedValue(list([]))
  api.lendDisc.mockResolvedValue(LOAN)
  api.returnLoan.mockResolvedValue({ ...LOAN, returnedDate: '2026-10-05' })
  api.confirmBarcode.mockResolvedValue({ barcode: CODE, source: 'cache', alreadyOwned: false, candidates: [] })
  api.fetchCopies.mockResolvedValue([
    { id: DISC, formats: ['bluray'], location: 'Front', section: 'Front', shelf: '3', edition: null, listingStatus: 'in_collection' } as unknown as CollectionCopy,
  ])
  api.fetchSearch.mockResolvedValue({ query: '', total: 0, items: [] })
  api.fetchSearchBeyond.mockResolvedValue({ query: '', items: [], unavailable: false })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

async function typeBarcode() {
  fireEvent.click(await screen.findByRole('button', { name: 'Lend or borrow' }))
  const starter = within(screen.getByRole('region', { name: 'Lend or borrow a disc' }))
  fireEvent.change(starter.getByLabelText('Or type the digits'), { target: { value: CODE } })
  fireEvent.click(starter.getByRole('button', { name: 'Look up' }))
  return starter
}

describe('Loans: lend or borrow from the page, by scan or search — Batch W3', () => {
  it('goes from a barcode to the film, its disc, and a borrow in your name', async () => {
    api.lookupBarcode.mockResolvedValue({
      barcode: CODE,
      source: 'ebay',
      alreadyOwned: false,
      candidates: [
        { title: 'Heat', source: 'ebay', confidence: 0.9, movieId: HEAT, tmdbId: 949, year: 1995, posterPath: null, evidence: null },
        { title: 'Heat Wave', source: 'ebay', confidence: 0.4, movieId: null, tmdbId: 1, year: 2009, posterPath: null, evidence: null },
      ],
    })
    renderLoans()
    const starter = await typeBarcode()

    // Only a film the catalogue knows can be lent; the stranger is not offered.
    fireEvent.click(await starter.findByRole('button', { name: 'Heat (1995)' }))
    expect(starter.queryByRole('button', { name: /Heat Wave/ })).toBeNull()

    await waitFor(() =>
      expect(api.confirmBarcode).toHaveBeenCalledWith({ barcode: CODE, title: 'Heat', source: 'ebay', movieId: HEAT, tmdbId: 949 }),
    )
    await waitFor(() => expect(api.fetchCopies).toHaveBeenCalledWith(HEAT))
    fireEvent.click(await starter.findByRole('button', { name: 'Borrow' }))
    fireEvent.click(starter.getByRole('button', { name: 'I’m borrowing it' }))

    await waitFor(() =>
      expect(api.lendDisc).toHaveBeenCalledWith({ collectionItemId: DISC, borrowerProfileId: MARK, dueDate: null }),
    )
  })

  it('says so when nothing in the catalogue matches the barcode', async () => {
    api.lookupBarcode.mockResolvedValue({ barcode: CODE, source: null, alreadyOwned: false, candidates: [] })
    renderLoans()
    const starter = await typeBarcode()

    expect(await starter.findByText(`Nothing in the catalogue matches ${CODE}. Search for the film instead.`)).not.toBeNull()
    expect(api.fetchCopies).not.toHaveBeenCalled()
  })

  it('lets a viewer say any loan is back, and calls it Returned', async () => {
    api.fetchLoans.mockResolvedValue(list([LOAN]))
    renderLoans()

    fireEvent.click(await screen.findByRole('button', { name: 'Returned' }))
    await waitFor(() => expect(api.returnLoan).toHaveBeenCalledWith(LOAN.id))
    expect(screen.queryByRole('button', { name: /Mark returned/ })).toBeNull()
  })

  it('shows your own borrow as with you', async () => {
    api.fetchLoans.mockResolvedValue(list([{ ...LOAN, borrowerName: 'Mark', borrowerProfileId: MARK }]))
    renderLoans()

    const row = (await screen.findByRole('link', { name: 'Heat' })).closest('li') as HTMLElement
    expect(within(row).getByText('you')).not.toBeNull()
  })
})
