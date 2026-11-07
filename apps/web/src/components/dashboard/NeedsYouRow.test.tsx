// @vitest-environment happy-dom
import { onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { NeedsYouItem } from '@mcu/shared'

const auth = vi.hoisted(() => ({ signedIn: true }))
vi.mock('@/context/auth', () => ({
  useAuth: () => ({
    profile: auth.signedIn
      ? { id: 'p-mark', displayName: 'Mark', role: 'viewer', hasPin: true, onboardingCompleted: true }
      : null,
  }),
}))

const api = vi.hoisted(() => ({ fetchNeedsYou: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))

import { needsYouCopy } from '@/lib/needs-you'

import { NeedsYouRow } from './NeedsYouRow'

const BASE: NeedsYouItem = {
  kind: 'putBack',
  loanId: '3f2504e0-4f89-41d3-9a0c-0305e82c3201',
  movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3301',
  movieTitle: 'Pulp Fiction',
  posterPath: null,
  locationLabel: 'Front 2nd',
  borrowerName: 'Craig',
  borrowerIsYou: false,
  lentDate: '2026-10-21',
  returnedDate: '2026-10-28',
  neededBy: null,
  dueDate: null,
  daysOverdue: null,
  daysOut: null,
}

function item(overrides: Partial<NeedsYouItem>): NeedsYouItem {
  return { ...BASE, ...overrides } as NeedsYouItem
}

function renderRow() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NeedsYouRow />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  auth.signedIn = true
  api.fetchNeedsYou.mockResolvedValue({ items: [] })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('needsYouCopy', () => {
  it('names the film, the action and where the disc goes', () => {
    expect(needsYouCopy(BASE)).toEqual({
      title: 'Put back Pulp Fiction',
      detail: 'Returned 28 Oct · goes to Front 2nd',
      to: `/loans?view=back&loan=${BASE.loanId}`,
    })
    expect(needsYouCopy(item({ locationLabel: 'Unfiled' })).detail).toBe('Returned 28 Oct · choose a shelf')
  })

  it('asks the shelf keeper to hand over a requested disc', () => {
    expect(needsYouCopy(item({ kind: 'handOver', borrowerName: 'Craig', lentDate: null, returnedDate: null, neededBy: '2026-11-06' }))).toEqual({
      title: 'Hand over Pulp Fiction',
      detail: 'Craig asked for it · needed by 6 Nov',
      to: `/loans?view=open&loan=${BASE.loanId}`,
    })
  })

  it('words an overdue loan for its borrower and for everyone else', () => {
    const late = item({ kind: 'overdue', lentDate: '2026-10-18', returnedDate: null, dueDate: '2026-11-01', daysOverdue: 3, daysOut: 17 })
    expect(needsYouCopy({ ...late, borrowerIsYou: true })).toMatchObject({
      title: 'Give back Pulp Fiction',
      detail: "You've had it since 18 Oct · 3 days overdue",
    })
    expect(needsYouCopy(late)).toMatchObject({
      title: 'Ask Craig for Pulp Fiction',
      detail: 'Lent 18 Oct · 3 days overdue',
      to: `/loans?view=open&loan=${BASE.loanId}`,
    })
    const open = item({ kind: 'overdue', lentDate: '2026-10-18', returnedDate: null, daysOut: 1 })
    expect(needsYouCopy(open).detail).toBe('Lent 18 Oct · out 1 day, no due date')
  })
})

describe('NeedsYouRow', () => {
  it('is hidden when nothing needs the person', async () => {
    renderRow()
    await vi.waitFor(() => expect(api.fetchNeedsYou).toHaveBeenCalled())
    expect(screen.queryByRole('region', { name: /Needs you/ })).toBeNull()
  })

  it('lists each job as a link to the exact place, most pressing first as the API orders them', async () => {
    api.fetchNeedsYou.mockResolvedValue({
      items: [
        item({ kind: 'overdue', movieTitle: 'Halloween', loanId: '3f2504e0-4f89-41d3-9a0c-0305e82c3202', lentDate: '2026-10-18', returnedDate: null, daysOut: 17 }),
        BASE,
      ],
    })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    const links = within(row).getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/loans?view=open&loan=3f2504e0-4f89-41d3-9a0c-0305e82c3202',
      `/loans?view=back&loan=${BASE.loanId}`,
    ])
    expect(links[0].textContent).toContain('Ask Craig for Halloween')
    expect(links[0].textContent).toContain('Lent 18 Oct · out 17 days, no due date')
    expect(links[1].textContent).toContain('Put back Pulp Fiction')
  })

  it('shows five and points at Loans for the rest', async () => {
    api.fetchNeedsYou.mockResolvedValue({
      items: Array.from({ length: 7 }, (_, index) => item({ movieTitle: `Film ${String(index)}`, loanId: `3f2504e0-4f89-41d3-9a0c-0305e82c32${String(10 + index)}` })),
    })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    expect(within(row).getAllByRole('listitem')).toHaveLength(5)
    expect(within(row).getByRole('link', { name: 'See all 7 on Loans' }).getAttribute('href')).toBe('/loans')
  })

  it('says so when the read fails, rather than looking like nothing to do', async () => {
    api.fetchNeedsYou.mockRejectedValue(new Error('Server error'))
    renderRow()
    expect(await screen.findByText('Could not check what needs you')).toBeTruthy()
  })

  it('says so offline with nothing kept, rather than looking like nothing to do', async () => {
    onlineManager.setOnline(false)
    try {
      renderRow()
      expect(await screen.findByText('What needs you is not cached here')).toBeTruthy()
      expect(api.fetchNeedsYou).not.toHaveBeenCalled()
    } finally {
      onlineManager.setOnline(true)
    }
  })

  it('asks nothing of the API for nobody signed in', async () => {
    auth.signedIn = false
    renderRow()
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(api.fetchNeedsYou).not.toHaveBeenCalled()
  })
})

describe('Next screening beside Needs you — AC2 (#337)', () => {
  const SCREENING = {
    sessionId: '3f2504e0-4f89-41d3-9a0c-0305e82c3901',
    plannedStart: '2026-11-07T20:00:00Z',
    withNames: ['Craig'],
    matchTitle: 'The Thing',
  }

  it('shows the next screening from the same read, with nothing else to do', async () => {
    api.fetchNeedsYou.mockResolvedValue({ items: [], nextScreening: SCREENING })
    renderRow()
    const link = await screen.findByRole('link', { name: /Next screening/ })
    expect(link.getAttribute('href')).toBe(`/movie-night/${SCREENING.sessionId}`)
    expect(link.textContent).toContain('7 Nov, 20:00')
    expect(link.textContent).toContain("with Craig · it's a match: The Thing")
    expect(screen.queryByRole('region', { name: /Needs you/ })).toBeNull()
    expect(api.fetchNeedsYou).toHaveBeenCalledTimes(1)
  })

  it('sits under the jobs when there are both', async () => {
    api.fetchNeedsYou.mockResolvedValue({ items: [BASE], nextScreening: { ...SCREENING, withNames: [], matchTitle: null } })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    const screening = screen.getByRole('link', { name: /Next screening/ })
    expect(row.compareDocumentPosition(screening)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    expect(screening.textContent).toContain('just you so far')
  })
})

describe('Cinema trips in Needs you and the top slot — AC5 (#345)', () => {
  const TRIP = '3f2504e0-4f89-41d3-9a0c-0305e82c3501'
  const invite = {
    kind: 'tripInvite' as const, tripId: TRIP, filmTitle: 'Wild Horse Nine', posterPath: null, venueName: 'ODEON Glasgow Quay',
    venueTimezone: 'Europe/London', startsAtUtc: '2026-11-09T20:10:00Z', proposerName: 'Craig', fromName: null, flag: null,
  }
  const nextTrip = { tripId: TRIP, filmTitle: 'Wild Horse Nine', venueName: 'ODEON Glasgow Quay', venueTimezone: 'Europe/London', startsAtUtc: '2026-11-09T20:10:00Z', withNames: ['Craig'] }
  const screening = (plannedStart: string) => ({ sessionId: '3f2504e0-4f89-41d3-9a0c-0305e82c3401', plannedStart, withNames: ['Craig'], matchTitle: null })

  it('puts a trip waiting for the reader’s reply before the discs, opening the trip', async () => {
    api.fetchNeedsYou.mockResolvedValue({ items: [BASE], nextScreening: null, trips: [invite], nextTrip: null })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    const links = within(row).getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual([`/movie-night/trips/${TRIP}`, `/loans?view=back&loan=${BASE.loanId}`])
    expect(links[0].textContent).toContain('Craig invited you: Wild Horse Nine, Mon 9 Nov 20:10')
    expect(within(row).getByText('2')).toBeTruthy()
  })

  it('gives the top slot to the next trip when it is sooner than the next screening', async () => {
    api.fetchNeedsYou.mockResolvedValue({ items: [], nextScreening: screening('2026-11-12T19:00:00Z'), trips: [], nextTrip })
    renderRow()
    const card = await screen.findByRole('link', { name: 'Next: Wild Horse Nine, Mon 9 Nov 20:10 at ODEON Glasgow Quay, with Craig' })
    expect(card.getAttribute('href')).toBe(`/movie-night/trips/${TRIP}`)
    expect(screen.queryByText(/Next screening/)).toBeNull()
  })

  it('keeps the screening in the slot when the screening is sooner', async () => {
    api.fetchNeedsYou.mockResolvedValue({ items: [], nextScreening: screening('2026-11-08T19:00:00Z'), trips: [], nextTrip })
    renderRow()
    expect(await screen.findByText('Next screening')).toBeTruthy()
    expect(screen.queryByRole('link', { name: /^Next: Wild Horse Nine/ })).toBeNull()
  })
})
