// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AssignedReview } from '@mcu/shared'

const auth = vi.hoisted(() => ({ role: 'viewer' }))
const api = vi.hoisted(() => ({ fetchAssignedReviews: vi.fn(), answerReview: vi.fn(), fetchReviewProposals: vi.fn(), assignReview: vi.fn(), fetchNeedsYou: vi.fn() }))
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
  api.fetchNeedsYou.mockResolvedValue({ items: [], trips: [], reviews: [] })
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

it('no longer carries the assigning control, for either person (AG3, UX54-03)', async () => {
  auth.role = 'admin'
  show()
  await screen.findByRole('region', { name: 'Everything waiting' })
  expect(screen.queryByRole('button', { name: 'Check current targets' })).toBeNull()
  expect(api.fetchReviewProposals).not.toHaveBeenCalled()
})

it('lists everything waiting for both, labelled, the reader’s own first (AE8)', async () => {
  api.fetchNeedsYou.mockResolvedValue({
    items: [{
      kind: 'handOver', loanId: 'loan-1', movieId: 'film-1', movieTitle: 'The Thing', posterPath: null, locationLabel: 'Front 2nd',
      borrowerName: 'Mark', borrowerIsYou: false, lentDate: null, returnedDate: null, neededBy: null, dueDate: null,
      daysOverdue: null, daysOut: null, owner: { profileId: 'craig', name: 'Craig' },
    }],
    trips: [],
    reviews: [{ ...review, assignedTo: 'mark' }],
  })
  show()
  const all = await screen.findByRole('region', { name: 'Everything waiting' })
  const rows = (await within(all).findAllByRole('listitem')).map((li) => li.textContent ?? '')
  expect(rows[0]).toContain("Check Titanic's Blu-ray")
  expect(rows[0]).toMatch(/You$/)
  expect(rows[1]).toContain('Craig to hand over The Thing')
  expect(rows[1]).toMatch(/Craig$/)
})


describe('AG11 (#390): a want’s question clears once the want is the film its answer names', () => {
  const want: AssignedReview = {
    ...review, kind: 'wanted_identity', title: "Check Dead Man's Shoes on Wanted",
    question: "Is the wanted film Dead Man's Shoes (2004) or Dead Man's Shoes (1940)?",
    choices: [{ value: '2004', label: "Dead Man's Shoes (2004)" }, { value: '1940', label: "Dead Man's Shoes (1940)" }, { value: 'unsure', label: 'Not sure yet' }],
    revision: 2, answer: '1940', status: 'resolved', canAnswer: false,
  }

  it('says it is resolved without claiming any catalogue work, for either person', async () => {
    for (const role of ['admin', 'viewer']) {
      auth.role = role
      api.fetchAssignedReviews.mockResolvedValue([want])
      api.fetchNeedsYou.mockResolvedValue({ items: [], trips: [], reviews: [] })
      show()
      const card = await screen.findByRole('region', { name: "Check Dead Man's Shoes on Wanted" })
      expect(within(card).getByText('For Mark · Resolved — the want is the film the answer names')).not.toBeNull()
      expect(within(card).queryByText(/through the catalogue|awaiting correction/)).toBeNull()
      expect(within(card).getByText("Recorded answer: Dead Man's Shoes (1940)")).not.toBeNull()
      expect(within(card).queryByRole('radio')).toBeNull()
      cleanup()
    }
  })

  it('keeps the catalogue wording for the other questions it is true of', async () => {
    api.fetchAssignedReviews.mockResolvedValue([{ ...review, status: 'resolved', canAnswer: false }])
    show()
    expect(await screen.findByText('For Mark · Resolved through the catalogue')).not.toBeNull()
  })
})
