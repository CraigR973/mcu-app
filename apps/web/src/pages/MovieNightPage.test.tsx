// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createMovieNight: vi.fn(),
  endMovieNight: vi.fn(),
  fetchMovieNights: vi.fn(),
  joinMovieNight: vi.fn(),
}))

vi.mock('@/lib/api', () => mocks)

vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: 'p', displayName: 'Craig', role: 'admin', hasPin: true, onboardingCompleted: true } }),
}))

import MovieNightPage from './MovieNightPage'

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/movie-night']}>
        <Routes>
          <Route path="/movie-night" element={<MovieNightPage />} />
          <Route path="/movie-night/:id" element={<p>The night</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('MovieNightPage — Batch V3', () => {
  it('starts a night with "Start movie night", not "Start swiping" (#228)', async () => {
    // A night is its shortlist now, with no deck to swipe.
    mocks.fetchMovieNights.mockResolvedValue({ items: [], total: 0 })
    mocks.createMovieNight.mockResolvedValue({ id: '3f2504e0-4f89-41d3-9a0c-0305e82c3401' })
    renderPage()

    expect(screen.queryByRole('button', { name: /Start swiping/ })).toBeNull()
    fireEvent.click(await screen.findByRole('button', { name: 'Start movie night' }))

    await waitFor(() => expect(mocks.createMovieNight).toHaveBeenCalledWith({}))
    expect(await screen.findByText('The night')).not.toBeNull()
  })
})


it('converts an optional planned local time into a UTC instant', async () => {
  mocks.fetchMovieNights.mockResolvedValue({ items: [], total: 0 })
  mocks.createMovieNight.mockResolvedValue({ id: '3f2504e0-4f89-41d3-9a0c-0305e82c3401' })
  renderPage()
  const input = screen.getByLabelText('Planned date and time (optional)')
  fireEvent.change(input, { target: { value: '2026-07-10T20:30' } })
  fireEvent.click(screen.getByRole('button', { name: 'Start movie night' }))
  await waitFor(() => expect(mocks.createMovieNight).toHaveBeenCalledWith({}, new Date('2026-07-10T20:30').toISOString()))
})

describe('MovieNightPage — AC4', () => {
  const night = (n: number, changes: Record<string, unknown>) => ({
    id: `3f2504e0-4f89-41d3-9a0c-0305e82c34${String(n).padStart(2, '0')}`, status: 'open', filters: {}, inviteToken: 'a'.repeat(16),
    invitePath: `/movie-night/join/${'a'.repeat(16)}`, participantCount: 1, plannedStart: null, createdAt: '2026-11-01T18:00:00Z', endedAt: null,
    people: [], invitable: [], match: null, ...changes,
  })

  it('folds ended and past screenings under "Past screenings (n)", closed, with open and planned on top', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-11-05T12:00:00Z'))
    mocks.fetchMovieNights.mockResolvedValue({
      items: [
        night(1, { status: 'ended', createdAt: '2026-10-20T18:00:00Z', endedAt: '2026-10-20T23:00:00Z' }),
        night(2, { plannedStart: '2026-11-07T19:30:00Z' }),
        night(3, { createdAt: '2026-11-04T18:00:00Z' }),
        night(4, { plannedStart: '2026-10-30T19:30:00Z' }),
        night(5, { plannedStart: '2026-11-05T20:00:00Z' }),
        night(6, { status: 'ended', createdAt: '2026-10-25T18:00:00Z', endedAt: '2026-10-25T23:00:00Z' }),
      ],
      total: 6,
    })
    renderPage()
    const open = await screen.findByRole('list', { name: 'Open and planned screenings' })
    // The soonest planned first, then an open night with no time.
    expect(within(open).getAllByRole('link').map((link) => link.getAttribute('href')?.slice(-2))).toEqual(['05', '02', '03'])
    const fold = screen.getByText('Past screenings (3)').closest('details')!
    expect(fold.open).toBe(false)
    expect(within(fold).getAllByRole('link').map((link) => link.getAttribute('href')?.slice(-2))).toEqual(['04', '06', '01'])
    // A past night still opens from the fold.
    fireEvent.click(screen.getByText('Past screenings (3)'))
    expect(fold.open).toBe(true)
    vi.restoreAllMocks()
  })

  it('sets "Plan a cinema trip" beside "Start a screening", opening At the cinema', async () => {
    mocks.fetchMovieNights.mockResolvedValue({ items: [], total: 0 })
    renderPage()
    const plan = await screen.findByRole('region', { name: 'Plan a cinema trip' })
    const start = screen.getByRole('heading', { name: 'Start a screening' }).closest('section')!
    expect(plan.parentElement).toBe(start.parentElement)
    expect(within(plan).getByRole('link', { name: 'See what’s on' }).getAttribute('href')).toBe('/movie-night/cinema')
    expect(screen.queryByText(/Past screenings/)).toBeNull()
  })

  it('is two views, At home and At the cinema, with the one open marked', async () => {
    mocks.fetchMovieNights.mockResolvedValue({ items: [], total: 0 })
    renderPage()
    const views = within(screen.getByRole('navigation', { name: 'Movie night views' }))
    expect(views.getByRole('link', { name: 'At home' }).getAttribute('aria-current')).toBe('page')
    expect(views.getByRole('link', { name: 'At the cinema' }).getAttribute('href')).toBe('/movie-night/cinema')
    expect(views.getByRole('link', { name: 'At the cinema' }).getAttribute('aria-current')).toBeNull()
  })
})
