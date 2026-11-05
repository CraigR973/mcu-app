// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CinemaFilms } from '@mcu/shared'

import { CINEMA_NOW, filmsFixture } from '@/pages/cinema-films-fixture'

const state = vi.hoisted(() => ({ id: 'craig', role: 'admin', online: true, fetch: vi.fn() }))
vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { id: state.id, role: state.role } }) }))
vi.mock('@/hooks/useOnlineStatus', () => ({ useOnlineStatus: () => state.online }))
vi.mock('@/lib/api', () => ({ fetchCinemaFilms: state.fetch, posterUrl: (path: string | null) => path ?? '/placeholder-poster.svg' }))
import { AtTheCinema } from './AtTheCinema'

function Where() {
  const { pathname, search } = useLocation()
  return <output aria-label="Address">{pathname + search}</output>
}

function setup(path = '/movie-night/cinema') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const tree = () => <QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AtTheCinema /><Where /></MemoryRouter></QueryClientProvider>
  return { ...render(tree()), tree }
}

const grid = (name: string) => screen.getByRole('region', { name })
const titles = (region: HTMLElement) => within(region).getAllByRole('article').map((card) => card.getAttribute('aria-label'))

beforeEach(() => {
  state.id = 'craig'; state.role = 'admin'; state.online = true
  vi.spyOn(Date, 'now').mockReturnValue(CINEMA_NOW)
  state.fetch.mockReset().mockResolvedValue(filmsFixture())
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('At the cinema, film first (AC4)', () => {
  it('puts this week’s films first, widest first, then what opens later, then listings and events', async () => {
    setup()
    await screen.findByRole('region', { name: 'This week' })
    expect(titles(grid('This week'))).toEqual(['A returning favourite', 'A current first run'])
    expect(titles(grid('Coming up'))).toEqual(['Opening later'])
    expect(titles(grid('Not matched to a film yet'))).toEqual(['An uncertain programme', 'Waiting film'])
    expect(titles(grid('Events and double bills'))).toEqual(['NT Live: Hamlet'])
    // Each film: its poster, its run, how many cinemas and its next showing.
    const favourite = within(grid('This week')).getByRole('article', { name: 'A returning favourite' })
    expect(within(favourite).getByText('Rerun')).toBeTruthy()
    expect(within(favourite).getByText('2 cinemas')).toBeTruthy()
    expect(within(favourite).getByText('Today 20:00')).toBeTruthy()
    expect(within(favourite).getByText('Seen')).toBeTruthy()
    expect(within(favourite).getByRole('link').getAttribute('href')).toBe('/movie-night/cinema/tmdb-1417')
    const fresh = within(grid('This week')).getByRole('article', { name: 'A current first run' })
    expect(within(fresh).getByText('First run')).toBeTruthy()
    expect(within(fresh).getByText('ODEON Kilmarnock')).toBeTruthy()
    expect(within(fresh).getByText('Thu 5 19:30')).toBeTruthy()
    // A listing says what it is where a film says its run.
    expect(within(grid('Not matched to a film yet')).getByText(/Not matched yet · Vue St Enoch/)).toBeTruthy()
  })

  it('says which cinemas list only to a date, and that coverage is partial', async () => {
    setup()
    const horizons = await screen.findByRole('region', { name: 'How far ahead cinemas list' })
    expect(within(horizons).getByText('Vue St Enoch: listed only to Wed 4 Nov')).toBeTruthy()
    expect(within(horizons).getByText('ODEON Kilmarnock: listed only to Mon 9 Nov')).toBeTruthy()
    expect(screen.getByText(/Partial coverage:/)).toBeTruthy()
  })

  it('filters by run with counts taken before the run, and keeps the choice in the address', async () => {
    setup()
    await screen.findByRole('region', { name: 'This week' })
    const runs = within(screen.getByRole('group', { name: 'Run' }))
    expect(runs.getAllByRole('button').map((button) => button.textContent)).toEqual(['All films6', 'New releases2', 'Older films1', 'Unclassified3'])
    fireEvent.click(runs.getByRole('button', { name: /^Older films/ }))
    expect(titles(grid('This week'))).toEqual(['A returning favourite'])
    expect(screen.queryByRole('region', { name: 'Coming up' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Not matched to a film yet' })).toBeNull()
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?run=olderFilm')
    fireEvent.click(runs.getByRole('button', { name: /^Unclassified/ }))
    expect(titles(grid('Not matched to a film yet'))).toEqual(['An uncertain programme', 'Waiting film'])
    expect(screen.queryByRole('region', { name: 'This week' })).toBeNull()
  })

  it('narrows to one day, and to the cinemas chosen, without another request', async () => {
    setup('/movie-night/cinema?day=2026-11-05')
    const day = await screen.findByRole('region', { name: 'Thu 5 Nov' })
    expect(titles(day)).toEqual(['A current first run'])
    fireEvent.click(within(screen.getByRole('group', { name: 'Day' })).getByRole('button', { name: 'Any day' }))
    fireEvent.click(screen.getByText('Cinemas · all nine'))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Vue Glasgow St Enoch' }))
    const favourite = within(grid('This week')).getByRole('article', { name: 'A returning favourite' })
    expect(within(favourite).getByText('ODEON Kilmarnock')).toBeTruthy()
    expect(screen.queryByRole('article', { name: 'An uncertain programme' })).toBeNull()
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?cinema=odeon-kilmarnock')
    fireEvent.click(screen.getByRole('checkbox', { name: 'ODEON Kilmarnock' }))
    expect(screen.getByText('Select at least one cinema.')).toBeTruthy()
    expect(screen.queryAllByRole('article')).toHaveLength(0)
    expect(state.fetch).toHaveBeenCalledTimes(1)
  })

  it('links Craig to the check a listing waits for, and shows Mark the state alone (AC3)', async () => {
    setup()
    const waiting = await screen.findByRole('article', { name: 'Waiting film' })
    expect(within(waiting).getByText(/Waiting for a check/)).toBeTruthy()
    expect(within(waiting).getByRole('link', { name: 'Check which film this is' }).getAttribute('href')).toBe('/identify')
    cleanup()
    state.id = 'mark'; state.role = 'viewer'
    setup()
    const marks = await screen.findByRole('article', { name: 'Waiting film' })
    expect(within(marks).getByText(/Waiting for a check/)).toBeTruthy()
    expect(within(marks).queryByRole('link', { name: 'Check which film this is' })).toBeNull()
  })

  it('drops a showing as it starts, on focus, without asking again', async () => {
    setup()
    await screen.findByRole('article', { name: 'A returning favourite' })
    vi.mocked(Date.now).mockReturnValue(Date.parse('2026-11-03T21:30:00Z'))
    fireEvent.focus(window)
    await waitFor(() => expect(screen.queryByRole('article', { name: 'A returning favourite' })).toBeNull())
    expect(state.fetch).toHaveBeenCalledTimes(1)
  })

  it('never draws another person’s watch marks while their own read is coming', async () => {
    const mounted = setup()
    await screen.findByText('Seen')
    state.fetch.mockImplementationOnce(() => new Promise<CinemaFilms>(() => undefined))
    state.id = 'mark'
    mounted.rerender(mounted.tree())
    await waitFor(() => expect(screen.queryByText('Seen')).toBeNull())
    expect(state.fetch).toHaveBeenCalledTimes(2)
  })

  it('keeps the nine official programmes when the first read fails, and says when offline', async () => {
    state.fetch.mockRejectedValueOnce(new Error('Unavailable'))
    setup()
    const fallback = await screen.findByRole('region', { name: 'Official cinema programmes' })
    expect(within(fallback).getAllByRole('link')).toHaveLength(9)
    cleanup()
    state.online = false
    setup()
    expect(await screen.findByText(/Offline · saved programme only/)).toBeTruthy()
  })

  it('says so when nothing is listed for a choice', async () => {
    const empty = filmsFixture(); empty.films = []
    state.fetch.mockResolvedValue(empty)
    setup('/movie-night/cinema?run=olderFilm')
    expect(await screen.findByText('No older films listed')).toBeTruthy()
    fireEvent.click(screen.getByText('Coverage and sources'))
    expect(screen.getByText('Source: CinemaTimes')).toBeTruthy()
  })
})
