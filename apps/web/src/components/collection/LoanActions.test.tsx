// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { Loan } from '@mcu/shared'

const api = vi.hoisted(() => ({ transitionLoan: vi.fn(), returnLoan: vi.fn(), fetchFacets: vi.fn() }))
vi.mock('@/lib/api', async (original) => ({ ...(await original<typeof import('@/lib/api')>()), ...api }))
import { LoanActions } from './LoanActions'

const loan: Loan = {
  id: '3f2504e0-4f89-41d3-9a0c-0305e82c3201', collectionItemId: '3f2504e0-4f89-41d3-9a0c-0305e82c3101', movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3301',
  movieTitle: 'Heat', posterPath: null, formats: ['blu_ray'], locationLabel: 'Front · 2nd', section: 'Front', shelf: '2nd',
  borrowerName: 'Craig', borrowerProfileId: null, lentDate: '2026-10-01', dueDate: null, returnedDate: '2026-10-02', isOverdue: false, daysUntilDue: null, notes: null, state: 'back', isCurrent: true,
}
function show(value = loan) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><LoanActions loan={value} /></QueryClientProvider>)
}
beforeEach(() => {
  api.transitionLoan.mockResolvedValue({ ...loan, state: 'shelved' })
  api.fetchFacets.mockResolvedValue({ allSections: ['Front', 'Back', 'Lounge'], sections: [] })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })
it('requires confirmation before shelving at the existing home position', async () => {
  show()
  fireEvent.click(screen.getByRole('button', { name: 'Put back' }))
  expect(api.transitionLoan).not.toHaveBeenCalled()
  expect(screen.getByText('Home position: Front · 2nd')).not.toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Confirm shelved' }))
  await waitFor(() => expect(api.transitionLoan).toHaveBeenCalledWith(loan.id, { state: 'shelved' }))
})
it('changes the actual section and shelf as part of the confirmation', async () => {
  show()
  fireEvent.click(screen.getByRole('button', { name: 'Put back' }))
  fireEvent.click(screen.getByLabelText('Change shelf'))
  await screen.findByRole('option', { name: 'Back' })
  fireEvent.change(screen.getByLabelText('Section'), { target: { value: 'Back' } })
  fireEvent.change(screen.getByLabelText('Shelf or side (optional)'), { target: { value: '3rd' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm shelved' }))
  await waitFor(() => expect(api.transitionLoan).toHaveBeenCalledWith(loan.id, { state: 'shelved', section: 'Back', shelf: '3rd' }))
})
it('keeps a failed confirmation visible and never claims the copy is shelved', async () => {
  api.transitionLoan.mockRejectedValue(new Error('A newer loan exists'))
  show()
  fireEvent.click(screen.getByRole('button', { name: 'Put back' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm shelved' }))
  expect(await screen.findByRole('alert')).not.toBeNull()
  expect(screen.getByRole('button', { name: 'Confirm shelved' })).not.toBeNull()
})
it('gives historical returns no physical action', () => {
  show({ ...loan, isCurrent: false })
  expect(screen.queryByRole('button')).toBeNull()
})
