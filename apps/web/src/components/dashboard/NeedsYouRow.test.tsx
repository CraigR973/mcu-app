// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
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

  it('asks nothing of the API for nobody signed in', async () => {
    auth.signedIn = false
    renderRow()
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(api.fetchNeedsYou).not.toHaveBeenCalled()
  })
})
