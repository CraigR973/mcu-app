// @vitest-environment happy-dom
import { onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { NeedsYouItem } from '@mcu/shared'

const auth = vi.hoisted(() => ({ signedIn: true, craig: false }))
vi.mock('@/context/auth', () => ({
  useAuth: () => ({
    profile: !auth.signedIn
      ? null
      : auth.craig
        ? { id: 'p-craig', displayName: 'Craig', role: 'admin', hasPin: true, onboardingCompleted: true }
        : { id: 'p-mark', displayName: 'Mark', role: 'viewer', hasPin: true, onboardingCompleted: true },
  }),
}))

const api = vi.hoisted(() => ({ fetchNeedsYou: vi.fn(), fetchAttention: vi.fn(), clearCraigNote: vi.fn() }))
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
  owner: null,
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
  auth.craig = false
  api.fetchNeedsYou.mockResolvedValue({ items: [] })
  api.fetchAttention.mockResolvedValue({ items: [], checkedAt: null })
  api.clearCraigNote.mockResolvedValue(undefined)
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
    // AE9: each row's own link comes first; its label is a link to whose it is.
    const links = within(row).getAllByRole('listitem').map((li) => within(li).getAllByRole('link')[0])
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/loans?view=open&loan=3f2504e0-4f89-41d3-9a0c-0305e82c3202',
      `/loans?view=back&loan=${BASE.loanId}`,
    ])
    expect(links[0].textContent).toContain('Ask Craig for Halloween')
    expect(links[0].textContent).toContain('Lent 18 Oct · out 17 days, no due date')
    expect(links[1].textContent).toContain('Put back Pulp Fiction')
  })

  it('shows five and points at Needs you for every one (AE8)', async () => {
    api.fetchNeedsYou.mockResolvedValue({
      items: Array.from({ length: 7 }, (_, index) => item({ movieTitle: `Film ${String(index)}`, loanId: `3f2504e0-4f89-41d3-9a0c-0305e82c32${String(10 + index)}` })),
    })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    expect(within(row).getAllByRole('listitem')).toHaveLength(5)
    expect(within(row).getByRole('link', { name: 'See all 7 on Needs you' }).getAttribute('href')).toBe('/needs-you')
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
    // AE9: each row's own link comes first; its label is a link to whose it is.
    const links = within(row).getAllByRole('listitem').map((li) => within(li).getAllByRole('link')[0])
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


it('exposes every item, reviews included, through the one overflow to Needs you (AE8)', async () => {
  const reviews = Array.from({ length: 3 }, (_, i) => ({
    id: `review-${i}`, title: `Review disc ${i}`, question: 'Inspect the physical disc', status: 'open',
  }))
  api.fetchNeedsYou.mockResolvedValue({ items: Array.from({ length: 5 }, (_, i) => item({ loanId: `loan-${i}` })), reviews })
  renderRow()
  expect((await screen.findByRole('link', { name: 'See all 8 on Needs you' })).getAttribute('href')).toBe('/needs-you')
  expect(screen.queryByText('Review disc 0')).toBeNull()
})

it('says whose each item is, the reader’s own first, in words for the reader (AE8)', async () => {
  const craig = { profileId: 'p-craig', name: 'Craig' }
  const mark = { profileId: 'p-mark', name: 'Mark' }
  const trip = {
    tripId: '3f2504e0-4f89-41d3-9a0c-0305e82c3401', filmTitle: 'Wild Horse Nine', posterPath: null, venueName: 'ODEON Glasgow Quay',
    venueTimezone: 'Europe/London', startsAtUtc: '2026-11-09T20:10:00Z', proposerName: 'Craig', fromName: null, flag: null,
  }
  api.fetchNeedsYou.mockResolvedValue({
    items: [
      item({ kind: 'handOver', movieTitle: 'The Thing', loanId: 'loan-thing', borrowerName: 'Mark', neededBy: '2026-11-12', owner: craig }),
      item({ movieTitle: 'Pulp Fiction', loanId: 'loan-pulp', owner: mark }),
    ],
    trips: [
      { ...trip, kind: 'tripWithdrawn', flag: 'withdrawn', owner: craig },
      { ...trip, kind: 'tripInvite', tripId: '3f2504e0-4f89-41d3-9a0c-0305e82c3402', owner: mark },
    ],
    reviews: [
      { id: 'review-craig', title: 'Check a box', question: 'Is it one box?', status: 'open', assignedTo: 'p-craig', assigneeName: 'Craig' },
    ],
  })
  renderRow()
  const row = await screen.findByRole('region', { name: /Needs you/ })
  const rows = within(row).getAllByRole('listitem').map((li) => li.textContent ?? '')
  expect(rows).toHaveLength(5)
  // Mark's own first: his invitation and the disc to put back; then Craig's three.
  expect(rows[0]).toContain('Craig invited you: Wild Horse Nine')
  expect(rows[0]).toMatch(/You$/)
  expect(rows[1]).toContain('Put back Pulp Fiction')
  expect(rows[2]).toContain('ODEON Glasgow Quay no longer lists Craig’s Wild Horse Nine time')
  expect(rows[2]).toContain('Craig picks another time or cancels.')
  expect(rows[2]).toMatch(/Craig$/)
  expect(rows[3]).toContain('Craig to hand over The Thing')
  expect(rows[3]).toContain('You asked for it · needed by 12 Nov')
  expect(rows[4]).toContain('For Craig · Is it one box?')
  // AE9 (#355): each label opens whose it is: Craig's page, or You for Mark's own.
  expect(within(row).getAllByRole('link', { name: 'Yours: open You' })[0].getAttribute('href')).toBe('/you')
  expect(within(row).getAllByRole('link', { name: 'Craig’s: open their page' })[0].getAttribute('href')).toBe('/people/p-craig')
})

it('shows an assigned review on Home even without loans or trips', async () => {
  api.fetchNeedsYou.mockResolvedValue({ items: [], reviews: [{ id: 'review-1', title: "Check Titanic's Blu-ray", question: 'Inspect the disc', status: 'answered' }] })
  renderRow()
  expect((await screen.findByRole('link', { name: /Check Titanic/ })).getAttribute('href')).toBe('/needs-you?review=review-1')
  expect(screen.getByText('Answered — awaiting correction')).not.toBeNull()
})

describe('AF1 (#372): Mark puts every disc back, and Craig’s Needs attention is part of Needs you', () => {
  const craig = { profileId: 'p-craig', name: 'Craig' }
  const mark = { profileId: 'p-mark', name: 'Mark' }
  const NOTE = '3f2504e0-4f89-41d3-9a0c-0305e82c3601'
  const problem = (key: string, message: string) => ({
    key, message, since: '2026-11-06T08:00:00Z', noteId: null, fromProfileId: null, fromName: null, body: null,
  })

  it('tells Craig a disc he gave back is Mark’s to put back, labelled Mark', async () => {
    auth.craig = true
    api.fetchNeedsYou.mockResolvedValue({ items: [item({ movieTitle: 'Halloween', borrowerIsYou: true, owner: mark })] })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    const [entry] = within(row).getAllByRole('listitem')
    expect(within(entry).getAllByRole('link')[0].textContent).toContain('Mark to put back Halloween')
    expect(entry.textContent).toContain('Returned 28 Oct · goes to Front 2nd')
    expect(within(entry).getByRole('link', { name: 'Mark’s: open their page' }).getAttribute('href')).toBe('/people/p-mark')
  })

  it('puts Craig’s app problems after his own items and before Mark’s, labelled App', async () => {
    auth.craig = true
    api.fetchNeedsYou.mockResolvedValue({
      items: [
        item({ kind: 'overdue', movieTitle: 'Glass Orchard', loanId: 'loan-glass', borrowerName: 'Dave', lentDate: '2026-10-18', returnedDate: null, daysOut: 26, owner: craig }),
        item({ movieTitle: 'Halloween', loanId: 'loan-halloween', owner: mark }),
      ],
    })
    api.fetchAttention.mockResolvedValue({
      checkedAt: '2026-11-13T08:00:00Z',
      items: [
        problem('identify:year-doubt', '1 identified film has a disc page or review for another year.'),
        problem('check:stale', 'The daily check has not run since 11 Nov.'),
      ],
    })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    await vi.waitFor(() => expect(within(row).getAllByRole('listitem')).toHaveLength(4))
    const entries = within(row).getAllByRole('listitem')
    const words = entries.map((entry) => entry.textContent ?? '')
    expect(words[0]).toContain('Ask Dave for Glass Orchard')
    expect(words[1]).toContain('1 identified film has a disc page')
    expect(words[2]).toContain('The daily check has not run')
    expect(words[3]).toContain('Mark to put back Halloween')
    // An App row opens where its Needs attention line did; one with nowhere to open says why.
    expect(within(entries[1]).getByRole('link').getAttribute('href')).toBe('/identify#identify-doubts-heading')
    expect(entries[1].textContent).toContain('Since 6 Nov · Open films in doubt')
    expect(within(entries[2]).queryByRole('link')).toBeNull()
    expect(entries[2].textContent).toContain('Railway')
    expect(within(entries[1]).getByText('App')).toBeTruthy()
    expect(within(row).getByText('4')).toBeTruthy()
    // No card of its own any more.
    expect(screen.queryByRole('heading', { name: 'Needs attention' })).toBeNull()
  })

  it('shows Craig a line from Mark as Mark’s row, which he clears', async () => {
    auth.craig = true
    api.fetchAttention.mockResolvedValue({
      checkedAt: null,
      items: [{ key: `note:${NOTE}`, message: 'Mark says: the Alien disc is in the Lounge', since: '2026-11-12T10:00:00Z', noteId: NOTE, fromProfileId: 'p-mark', fromName: 'Mark', body: 'the Alien disc is in the Lounge' }],
    })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    const [line] = within(row).getAllByRole('listitem')
    expect(line.textContent).toContain('the Alien disc is in the Lounge')
    expect(line.textContent).toContain('Tell Craig · 12 Nov')
    expect(within(line).getByRole('link', { name: 'Mark’s: open their page' }).getAttribute('href')).toBe('/people/p-mark')
    fireEvent.click(within(line).getByRole('button', { name: /Clear/ }))
    await vi.waitFor(() => expect(api.clearCraigNote).toHaveBeenCalledWith(NOTE))
  })

  it('never leaves what has stopped to See all, past Home’s five', async () => {
    auth.craig = true
    api.fetchNeedsYou.mockResolvedValue({
      items: Array.from({ length: 6 }, (_, index) => item({ movieTitle: `Film ${String(index)}`, loanId: `loan-${String(index)}`, owner: craig })),
    })
    api.fetchAttention.mockResolvedValue({ checkedAt: null, items: [problem('job:cron-ebay', 'The eBay job has not run since 10 Nov.')] })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    await vi.waitFor(() => expect(within(row).getByText(/The eBay job has not run/)).toBeTruthy())
    expect(within(row).getAllByRole('listitem')).toHaveLength(6)
    expect(within(row).getByRole('link', { name: 'See all 7 on Needs you' })).toBeTruthy()
  })

  it('shows every app row on top of Home’s five, so they never push Mark’s items off Home', async () => {
    auth.craig = true
    api.fetchNeedsYou.mockResolvedValue({
      items: [
        ...Array.from({ length: 3 }, (_, index) => item({ movieTitle: `Own ${String(index)}`, loanId: `own-${String(index)}`, owner: craig })),
        ...Array.from({ length: 3 }, (_, index) => item({ movieTitle: `Marks ${String(index)}`, loanId: `mark-${String(index)}`, owner: mark })),
      ],
    })
    api.fetchAttention.mockResolvedValue({
      checkedAt: null,
      items: ['job:cron-ebay', 'job:cron-scrape', 'check:stale'].map((key) => problem(key, `Problem ${key}`)),
    })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    await vi.waitFor(() => expect(within(row).getByText('Problem check:stale')).toBeTruthy())
    const words = within(row).getAllByRole('listitem').map((entry) => entry.textContent ?? '')
    // Five of the people's items, as before AF1: Craig's three, then two of Mark's, with the
    // three app rows between them.
    expect(words).toHaveLength(8)
    expect(words.slice(0, 3).every((text) => text.includes('Own'))).toBe(true)
    expect(words.slice(3, 6).every((text) => text.includes('Problem'))).toBe(true)
    expect(words[6]).toContain('Mark to put back Marks 0')
    expect(words[7]).toContain('Mark to put back Marks 1')
    expect(within(row).getByRole('link', { name: 'See all 9 on Needs you' })).toBeTruthy()
  })

  it('shows the app’s problems with nothing else waiting', async () => {
    auth.craig = true
    api.fetchAttention.mockResolvedValue({ checkedAt: null, items: [problem('database:size', 'The database is 80% full.')] })
    renderRow()
    const row = await screen.findByRole('region', { name: /Needs you/ })
    expect(within(row).getByText('The database is 80% full.')).toBeTruthy()
  })

  it('never asks the API for the app’s problems for Mark', async () => {
    api.fetchNeedsYou.mockResolvedValue({ items: [item({ owner: mark })] })
    renderRow()
    await screen.findByRole('region', { name: /Needs you/ })
    expect(api.fetchAttention).not.toHaveBeenCalled()
    expect(screen.queryByText('App')).toBeNull()
  })
})
