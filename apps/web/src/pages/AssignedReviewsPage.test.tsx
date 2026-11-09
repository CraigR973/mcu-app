// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { AssignedReview } from '@mcu/shared'

const auth = vi.hoisted(() => ({ role: 'viewer' }))
const api = vi.hoisted(() => ({ fetchAssignedReviews: vi.fn(), answerReview: vi.fn(), fetchReviewProposals: vi.fn(), assignReview: vi.fn() }))
vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { id: 'mark', role: auth.role } }) }))
vi.mock('@/lib/api', async original => ({ ...(await original<typeof import('@/lib/api')>()), ...api }))
import AssignedReviewsPage from './AssignedReviewsPage'

const review: AssignedReview = {
  id: '0b6ccc42-9b9c-4e85-8d81-f476772e997a', kind: 'titanic_disc',
  targetId: '3c8bb48b-ac07-4157-bf70-b31c0afc9681', assignedTo: '30738655-a32f-4004-815d-f4e753c3235b',
  assigneeName: 'Mark', movieId: '8e25a5a4-ffcd-496d-aefc-d3cc9a5d8d67', title: "Check Titanic's Blu-ray",
  question: 'Is this disc Titanic (1953) or Titanic (1997)?', evidence: 'Inspect this physical disc.',
  choices: [{ value: '1953', label: 'Titanic (1953)' }, { value: '1997', label: 'Titanic (1997)' }, { value: 'unsure', label: 'Not sure yet' }],
  revision: 1, answer: null, answeredAt: null, status: 'open', canAnswer: true,
}

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter><AssignedReviewsPage /></MemoryRouter></QueryClientProvider>)
}
beforeEach(() => {
  auth.role = 'viewer'
  api.fetchAssignedReviews.mockResolvedValue([review])
  api.answerReview.mockResolvedValue({ ...review, revision: 2, answer: 'unsure' })
})
afterEach(() => { cleanup(); vi.resetAllMocks() })

it('records an uncertain observation with the shown revision, without an identity action', async () => {
  show()
  const card = await screen.findByRole('region', { name: "Check Titanic's Blu-ray" })
  expect(within(card).getByRole('link', { name: 'Inspect the film and copies' }).getAttribute('href')).toBe(`/movies/${review.movieId}`)
  expect(within(card).getByRole('button', { name: 'Save observation' }).hasAttribute('disabled')).toBe(true)
  fireEvent.click(within(card).getByRole('radio', { name: 'Not sure yet' }))
  fireEvent.click(within(card).getByRole('button', { name: 'Save observation' }))
  await vi.waitFor(() => expect(api.answerReview).toHaveBeenCalledWith(review.id, 1, 'unsure'))
  expect(api.assignReview).not.toHaveBeenCalled()
  expect(api.fetchAssignedReviews).toHaveBeenCalledWith(false)
  expect(screen.queryByRole('button', { name: 'Check current targets' })).toBeNull()
})

it('shows a changed target honestly and offers no answer form', async () => {
  api.fetchAssignedReviews.mockResolvedValue([{ ...review, status: 'changed', canAnswer: false }])
  show()
  expect(await screen.findByText('For Mark · The record changed — needs another look')).not.toBeNull()
  expect(screen.queryByRole('radio')).toBeNull()
})

it('lets Craig inspect an answer without answering on Mark’s behalf or assigning on read', async () => {
  auth.role = 'admin'
  api.fetchAssignedReviews.mockResolvedValue([{ ...review, status: 'answered', answer: '1997', canAnswer: false }])
  show()
  expect(await screen.findByText('Recorded answer: Titanic (1997)')).not.toBeNull()
  expect(api.fetchAssignedReviews).toHaveBeenCalledWith(true)
  expect(screen.queryByRole('radio')).toBeNull()
  expect(api.fetchReviewProposals).not.toHaveBeenCalled()
  expect(api.assignReview).not.toHaveBeenCalled()
})

it('does not present a failed review read as an empty queue', async () => {
  api.fetchAssignedReviews.mockRejectedValue(new Error('Unavailable'))
  show()
  expect(await screen.findByText('Could not load reviews')).not.toBeNull()
  expect(screen.queryByText('No assigned reviews')).toBeNull()
})

it('checks the three current targets without assigning, then assigns only on the explicit click', async () => {
  auth.role = 'admin'
  const proposals = ['titanic_disc', 'wanted_identity', 'shetland_series'].map(kind => ({
    kind, targetId: review.targetId, assignedTo: review.assignedTo,
    expectedFingerprint: 'a'.repeat(64), title: kind,
  }))
  api.fetchReviewProposals.mockResolvedValue(proposals)
  api.assignReview.mockResolvedValue(review)
  show()
  fireEvent.click(await screen.findByRole('button', { name: 'Check current targets' }))
  const assign = await screen.findByRole('button', { name: 'Assign these three reviews to Mark' })
  expect(api.assignReview).not.toHaveBeenCalled()
  fireEvent.click(assign)
  await vi.waitFor(() => expect(api.assignReview).toHaveBeenCalledTimes(3))
  for (const proposal of proposals) expect(api.assignReview).toHaveBeenCalledWith(proposal)
})
