// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Loan } from '@mcu/shared'

const auth = vi.hoisted(() => ({ id: '3f2504e0-4f89-41d3-9a0c-0305e82c3001', name: 'Mark', role: 'viewer' as 'admin' | 'viewer' }))
vi.mock('@/context/auth', () => ({
  useAuth: () => ({
    profile: { id: auth.id, displayName: auth.name, role: auth.role, hasPin: true, onboardingCompleted: true },
  }),
}))

const api = vi.hoisted(() => ({ fetchLoans: vi.fn(), lendDisc: vi.fn(), returnLoan: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))

import { LendButton } from './LendButton'

const ITEM = '3f2504e0-4f89-41d3-9a0c-0305e82c3101'

function loan(overrides: Partial<Loan>): Loan {
  return {
    id: '3f2504e0-4f89-41d3-9a0c-0305e82c3201',
    collectionItemId: ITEM,
    movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3301',
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
    ...overrides,
  }
}

function list(items: Loan[]) {
  return { items, total: items.length, openCount: items.length, overdueCount: 0 }
}

function renderButton() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <LendButton collectionItemId={ITEM} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  auth.role = 'viewer'
  api.fetchLoans.mockResolvedValue(list([]))
  api.lendDisc.mockResolvedValue(loan({}))
  api.returnLoan.mockResolvedValue(loan({ returnedDate: '2026-10-05' }))
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Lend, borrow and returned on a disc — Batch W3', () => {
  it('offers Lend and Borrow to a viewer, who could do neither before W3', async () => {
    renderButton()
    expect(await screen.findByRole('button', { name: 'Lend' })).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Borrow' })).not.toBeNull()
  })

  it('records a borrow as the person, with no name to type', async () => {
    renderButton()
    fireEvent.click(await screen.findByRole('button', { name: 'Borrow' }))
    expect(screen.queryByLabelText('Borrower')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'I’m borrowing it' }))

    await waitFor(() =>
      expect(api.lendDisc).toHaveBeenCalledWith({ collectionItemId: ITEM, borrowerProfileId: auth.id, dueDate: null }),
    )
  })

  it('asks for a name to lend, and sends the name', async () => {
    renderButton()
    fireEvent.click(await screen.findByRole('button', { name: 'Lend' }))
    fireEvent.change(screen.getByLabelText('Borrower'), { target: { value: '  Dave ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Lend it' }))

    await waitFor(() =>
      expect(api.lendDisc).toHaveBeenCalledWith({ collectionItemId: ITEM, borrowerName: 'Dave', dueDate: null }),
    )
  })

  it('says "With you" for your own borrow, and lets you say it is back', async () => {
    api.fetchLoans.mockResolvedValue(list([loan({ borrowerName: 'Mark', borrowerProfileId: auth.id })]))
    renderButton()

    expect(await screen.findByText('With you')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Returned' }))
    await waitFor(() => expect(api.returnLoan).toHaveBeenCalledWith('3f2504e0-4f89-41d3-9a0c-0305e82c3201'))
  })

  it('names anyone else who has it', async () => {
    api.fetchLoans.mockResolvedValue(list([loan({})]))
    renderButton()

    expect(await screen.findByText('Dave')).not.toBeNull()
    expect(screen.queryByText('With you')).toBeNull()
    expect(screen.getByRole('button', { name: 'Returned' })).not.toBeNull()
    expect(screen.queryByRole('button', { name: /Mark returned/ })).toBeNull()
  })
})

it('requests a copy for yourself with needed-by and no invented lent date', async () => {
  renderButton()
  fireEvent.click(await screen.findByRole('button', { name: 'Ask to borrow' }))
  fireEvent.change(screen.getByLabelText('Needed by'), { target: { value: '2026-11-03' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send request' }))
  await waitFor(() => expect(api.lendDisc).toHaveBeenCalledWith({ collectionItemId: ITEM, borrowerProfileId: auth.id, state: 'asked_for', neededBy: '2026-11-03' }))
})

it('shows asked-for without claiming the disc is with the borrower', async () => {
  api.fetchLoans.mockResolvedValue(list([loan({ state: 'asked_for', neededBy: '2026-11-03', lentDate: null })]))
  renderButton()
  expect(await screen.findByText('Asked for')).not.toBeNull()
  expect(screen.getByRole('button', { name: 'Taken' })).not.toBeNull()
  expect(screen.queryByRole('button', { name: 'Returned' })).toBeNull()
  expect(screen.queryByText('With you')).toBeNull()
})
