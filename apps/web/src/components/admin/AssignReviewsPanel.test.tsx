// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ fetchReviewProposals: vi.fn(), fetchWantProposals: vi.fn(), assignReview: vi.fn() }))
vi.mock('@/lib/api', async original => ({ ...(await original<typeof import('@/lib/api')>()), ...api }))
import { AssignReviewsPanel } from './AssignReviewsPanel'

afterEach(() => { cleanup(); vi.resetAllMocks() })

// AG3 (UX54-03): moved from the Needs you page's tests; the behaviour is unchanged.
it('checks the three current targets without assigning, then assigns only on the explicit click', async () => {
  const review = { targetId: '3c8bb48b-ac07-4157-bf70-b31c0afc9681', assignedTo: '30738655-a32f-4004-815d-f4e753c3235b' }
  const proposals = ['titanic_disc', 'wanted_identity', 'shetland_series'].map(kind => ({
    kind, targetId: review.targetId, assignedTo: review.assignedTo,
    expectedFingerprint: 'a'.repeat(64), title: kind,
  }))
  api.fetchReviewProposals.mockResolvedValue(proposals)
  api.assignReview.mockResolvedValue(review)
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><AssignReviewsPanel /></QueryClientProvider>)
  expect(api.fetchReviewProposals).not.toHaveBeenCalled()
  fireEvent.click(await screen.findByRole('button', { name: 'Check current targets' }))
  const assign = await screen.findByRole('button', { name: 'Assign these three reviews to Mark' })
  expect(api.assignReview).not.toHaveBeenCalled()
  fireEvent.click(assign)
  await vi.waitFor(() => expect(api.assignReview).toHaveBeenCalledTimes(3))
  for (const proposal of proposals) expect(api.assignReview).toHaveBeenCalledWith(proposal)
})

// AG5 (MK53-03): any want can ask which film, one at a time, only on its own click.
it('lists the wants whose shops name another film and asks one only on its click', async () => {
  const proposal = {
    kind: 'wanted_identity', targetId: '3c8bb48b-ac07-4157-bf70-b31c0afc9681',
    assignedTo: '30738655-a32f-4004-815d-f4e753c3235b', expectedFingerprint: 'a'.repeat(64),
    title: 'Check Bad Lieutenant: Port of Call New Orleans on Wanted',
    question: 'Is the wanted film Bad Lieutenant: Port of Call New Orleans (2009) or Bad Lieutenant (1992)?',
    choices: [{ value: '2009', label: 'Bad Lieutenant: Port of Call New Orleans (2009)' }, { value: '1992', label: 'Bad Lieutenant (1992)' }],
    assigneeName: 'Viewer',
  }
  api.fetchWantProposals.mockResolvedValueOnce([proposal]).mockResolvedValue([])
  api.assignReview.mockResolvedValue({})
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}><AssignReviewsPanel /></QueryClientProvider>)
  expect(api.fetchWantProposals).not.toHaveBeenCalled()
  fireEvent.click(await screen.findByRole('button', { name: 'Check wants' }))
  expect(await screen.findByText(proposal.question)).toBeTruthy()
  expect(api.assignReview).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Ask Viewer' }))
  await vi.waitFor(() => expect(api.assignReview).toHaveBeenCalledWith(proposal))
  expect(await screen.findByText('No want’s shops list another film.')).toBeTruthy()
})
