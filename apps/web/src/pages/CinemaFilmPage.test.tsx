// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CinemaFilmDetail } from '@mcu/shared'

import { CINEMA_NOW, detailFixture, ODEON, showingFixture, VUE } from './cinema-films-fixture'

const state = vi.hoisted(() => ({ id: 'craig', role: 'admin', online: true, fetch: vi.fn() }))
vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { id: state.id, role: state.role } }) }))
vi.mock('@/hooks/useOnlineStatus', () => ({ useOnlineStatus: () => state.online }))
vi.mock('@/lib/api', () => {
  class ApiError extends Error {
    constructor(message: string, readonly status: number) { super(message) }
  }
  return { ApiError, fetchCinemaFilm: state.fetch, posterUrl: (path: string | null) => path ?? '/placeholder-poster.svg' }
})
import { ApiError } from '@/lib/api'
import CinemaFilmPage from './CinemaFilmPage'

function Where() {
  return <output aria-label="Address">{useLocation().pathname}</output>
}

function setup(key = 'tmdb-1417') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const tree = () => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/movie-night/cinema/${key}`]}>
        <Routes><Route path="/movie-night/cinema/:key" element={<CinemaFilmPage />} /></Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>
  )
  return { ...render(tree()), tree }
}

const tickets = () => screen.queryAllByRole('link', { name: /check tickets/ })

beforeEach(() => {
  state.id = 'craig'; state.role = 'admin'; state.online = true
  vi.spyOn(Date, 'now').mockReturnValue(CINEMA_NOW)
  state.fetch.mockReset().mockResolvedValue(detailFixture())
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('a film’s every showing across the nine (AC4)', () => {
  it('groups showings by day, then cinema, as time chips with their format', async () => {
    setup()
    const today = await screen.findByRole('region', { name: 'Today · Tue 3 Nov' })
    const tomorrow = screen.getByRole('region', { name: 'Tomorrow · Wed 4 Nov' })
    expect(within(today).getAllByRole('listitem', { name: /Vue|ODEON/ }).map((item) => item.getAttribute('aria-label'))).toEqual(['Vue Glasgow St Enoch', 'ODEON Kilmarnock'])
    const vue = within(today).getByRole('listitem', { name: 'Vue Glasgow St Enoch' })
    const imax = within(vue).getByRole('link', { name: '20:00 IMAX · Screen 4, check tickets at Vue Glasgow St Enoch' })
    expect(imax.getAttribute('href')).toBe('https://www.myvue.com/book-tickets/summary/10097/1')
    expect(imax.getAttribute('rel')).toBe('noopener noreferrer')
    expect(imax.getAttribute('referrerpolicy')).toBe('no-referrer')
    expect(imax.getAttribute('target')).toBe('_blank')
    // "Digital projection" is said once for the cinema, not on every time; no enum syntax shows.
    const odeon = within(today).getByRole('listitem', { name: 'ODEON Kilmarnock' })
    expect(within(odeon).getByText('Digital projection')).toBeTruthy()
    expect(within(odeon).getByRole('link', { name: '21:00, check tickets at ODEON Kilmarnock' })).toBeTruthy()
    expect(screen.queryByText(/Format\.Projection/)).toBeNull()
    expect(tickets()).toHaveLength(3)
    expect(within(tomorrow).getByText('Listed as “A returning favourite (35th Anniversary)”')).toBeTruthy()
    expect(within(today).getAllByRole('link', { name: 'Official programme' })).toHaveLength(2)
  })

  it('keeps each showing’s run reason: once for the film, or per cinema where they differ (AC3)', async () => {
    setup()
    await screen.findByRole('heading', { name: 'A returning favourite', level: 1 })
    expect(screen.getByText('Rerun')).toBeTruthy()
    const tomorrow = screen.getByRole('region', { name: 'Tomorrow · Wed 4 Nov' })
    expect(within(tomorrow).getByText('UK release 1990 · the cinema calls it an anniversary showing · rerun')).toBeTruthy()
    expect(within(screen.getByRole('region', { name: 'Today · Tue 3 Nov' })).getAllByText('UK release 1990 · rerun')).toHaveLength(2)
    cleanup()
    const same = detailFixture(); same.showings = same.showings.slice(0, 2); state.fetch.mockResolvedValue(same)
    setup()
    expect(await screen.findByText('UK release 1990 · rerun')).toBeTruthy()
  })

  it('names the reader’s own watch and the collection, with the way to the archive', async () => {
    setup()
    expect(await screen.findByText('In the collection · You have watched this')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Open in the archive' }).getAttribute('href')).toBe('/movies/00000000-0000-4000-8000-000000000090')
    expect(screen.getByText(/Showing at 2 cinemas · next Today 20:00, Vue St Enoch/)).toBeTruthy()
  })

  it('pauses every ticket link offline, keeping the official programmes', async () => {
    const mounted = setup()
    await waitFor(() => expect(tickets()).toHaveLength(3))
    state.online = false
    mounted.rerender(mounted.tree())
    expect(tickets()).toHaveLength(0)
    expect(screen.getAllByRole('link', { name: 'Official programme' }).length).toBeGreaterThan(0)
    expect(screen.getByText(/Offline · saved programme only/)).toBeTruthy()
  })

  it('drops a started showing’s link when the page regains focus, without a new answer', async () => {
    setup()
    await waitFor(() => expect(tickets()).toHaveLength(3))
    vi.mocked(Date.now).mockReturnValue(Date.parse('2026-11-03T20:30:00Z'))
    fireEvent.focus(window)
    await waitFor(() => expect(tickets()).toHaveLength(2))
    expect(state.fetch).toHaveBeenCalledTimes(1)
  })

  it('shows a failed check’s and an unconfirmed showing’s times with no ticket link', async () => {
    const detail = detailFixture()
    detail.venues[0].coverage[0] = { ...detail.venues[0].coverage[0], status: 'failed' }
    detail.showings[2] = showingFixture(3, ODEON, '2026-11-04T18:30:00Z', { confirmation: 'unconfirmed' })
    state.fetch.mockResolvedValue(detail)
    setup()
    const vue = within(await screen.findByRole('region', { name: 'Today · Tue 3 Nov' })).getByRole('listitem', { name: 'Vue Glasgow St Enoch' })
    expect(within(vue).getByText('Latest check failed · ticket links paused')).toBeTruthy()
    expect(within(vue).queryAllByRole('link', { name: /check tickets/ })).toHaveLength(0)
    expect(within(vue).getByLabelText('20:00 IMAX · Screen 4, no ticket link')).toBeTruthy()
    const tomorrow = screen.getByRole('region', { name: 'Tomorrow · Wed 4 Nov' })
    expect(within(tomorrow).getByText('Unconfirmed')).toBeTruthy()
    expect(within(tomorrow).getByLabelText('18:30, showing unconfirmed')).toBeTruthy()
    expect(tickets()).toHaveLength(1)
    expect(screen.getByText(/Some saved programmes are stale or their latest check failed/)).toBeTruthy()
  })

  it('says a listing waits for a check, links Craig to it, and shows Mark the state alone (AC3)', async () => {
    const listing = detailFixture()
    listing.film = { ...listing.film, key: 'listing-00000000-0000-4000-8000-000000000051', kind: 'listing', title: 'Waiting film', identityStatus: 'review', identityReason: 'the title matches, but nothing else agrees', tmdbId: null, movieId: null, owned: null, watched: null, originalYear: null, posterPath: null }
    listing.showings = [showingFixture(4, ODEON, '2026-11-04T18:00:00Z', { sourceTitle: 'Waiting film', releaseCategory: 'unclassified', categoryReason: null, categoryConfidence: 'unverified' })]
    state.fetch.mockResolvedValue(listing)
    setup(listing.film.key)
    const check = await screen.findByRole('region', { name: 'Which film this is' })
    expect(within(check).getByText('Identity waiting for a check · possible duplicate programme')).toBeTruthy()
    expect(within(check).getByRole('link', { name: 'Check which film this is' }).getAttribute('href')).toBe('/identify')
    expect(screen.queryByText('Rerun')).toBeNull()
    cleanup()
    state.id = 'mark'; state.role = 'viewer'
    setup(listing.film.key)
    const marks = await screen.findByRole('region', { name: 'Which film this is' })
    expect(within(marks).getByText(/Identity waiting for a check/)).toBeTruthy()
    expect(within(marks).queryByRole('link', { name: 'Check which film this is' })).toBeNull()
  })

  it('never gives an event a year or a film', async () => {
    const event = detailFixture()
    event.film = { ...event.film, key: 'listing-00000000-0000-4000-8000-000000000052', kind: 'event', title: 'NT Live: Hamlet', identityStatus: 'event', tmdbId: null, movieId: null, owned: null, watched: null, originalYear: null }
    event.showings = [showingFixture(5, ODEON, '2026-11-06T19:00:00Z', { sourceTitle: 'NT Live: Hamlet', releaseCategory: 'unclassified', categoryReason: null })]
    state.fetch.mockResolvedValue(event)
    setup(event.film.key)
    expect(await screen.findByText('An event or double bill, not one film')).toBeTruthy()
    expect(screen.queryByText(/1990|Open in the archive|About the film/)).toBeNull()
  })

  it('opens a listing linked since as the film, under the film’s address', async () => {
    setup('listing-00000000-0000-4000-8000-000000000050')
    await waitFor(() => expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema/tmdb-1417'))
    expect(await screen.findByRole('heading', { name: 'A returning favourite', level: 1 })).toBeTruthy()
    expect(state.fetch).toHaveBeenCalledTimes(1)
  })

  it('says a film is not listed now, and a page it does not know, without a stale action', async () => {
    const quiet = detailFixture(); quiet.showings = []
    state.fetch.mockResolvedValue(quiet)
    setup()
    expect(await screen.findByText('No showings listed now')).toBeTruthy()
    expect(tickets()).toHaveLength(0)
    cleanup()
    state.fetch.mockRejectedValue(new ApiError('No such film at your cinemas', 404))
    setup('tmdb-9')
    expect(await screen.findByText('Not listed at your cinemas')).toBeTruthy()
  })

  it('never draws another person’s watch while their own read is coming', async () => {
    const mounted = setup()
    await screen.findByText(/You have watched this/)
    state.fetch.mockImplementationOnce(() => new Promise<CinemaFilmDetail>(() => undefined))
    state.id = 'mark'
    mounted.rerender(mounted.tree())
    await waitFor(() => expect(screen.queryByText(/You have watched this/)).toBeNull())
    expect(tickets()).toHaveLength(0)
  })

  it('points a listing at others of its title, which may or may not be the same film', async () => {
    const detail = detailFixture()
    detail.alsoListed = [{ key: 'listing-00000000-0000-4000-8000-000000000060', kind: 'listing', title: 'A returning favourite', venueIds: [VUE], showingCount: 2 }]
    state.fetch.mockResolvedValue(detail)
    setup()
    const also = await screen.findByRole('region', { name: 'Also listed under this title' })
    const link = within(also).getByRole('link')
    expect(link.getAttribute('href')).toBe('/movie-night/cinema/listing-00000000-0000-4000-8000-000000000060')
    expect(link.textContent).toContain('Not matched yet · Vue St Enoch · 2 showings')
  })
})
