// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CinemaProgrammeResponse } from '@mcu/shared'
import { cinemaFixture, CINEMA_NOW } from './cinema-test-fixture'
const state = vi.hoisted(() => ({ id: 'craig', online: true, fetch: vi.fn() }))
vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { id: state.id } }) }))
vi.mock('@/hooks/useOnlineStatus', () => ({ useOnlineStatus: () => state.online }))
vi.mock('@/lib/api', () => ({ fetchCinemaProgramme: state.fetch }))
import CinemasPage from './CinemasPage'
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const tree = () => <QueryClientProvider client={client}><MemoryRouter><CinemasPage /></MemoryRouter></QueryClientProvider>
  const result = render(tree())
  return { ...result, tree, client }
}
beforeEach(() => { state.id = 'craig'; state.online = true; vi.spyOn(Date, 'now').mockReturnValue(CINEMA_NOW); state.fetch.mockReset().mockResolvedValue(cinemaFixture()) })
afterEach(() => { cleanup(); vi.restoreAllMocks() })
describe('stored cinema discovery', () => {
  it('keeps watched older favourites, multiple venues, unknowns and category counts distinct', async () => {
    const p = cinemaFixture(); p.films[0].showings[0].screen = '2'; p.films[0].showings[0].formats = ['Format.Projection.Digital']; state.fetch.mockResolvedValue(p)
    setup()
    const card = await screen.findByRole('article', { name: 'A returning favourite' })
    expect(within(card).getByText('You have watched this', { exact: false })).toBeTruthy()
    expect(within(card).getAllByRole('link', { name: 'Check tickets' })).toHaveLength(2)
    expect(within(card).getByText('Older films · Reissue · Screen 2 · Digital projection')).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Older films (2 screenings)' })).toBeTruthy()
    expect(screen.getAllByText('Year unverified', { exact: false })).toHaveLength(2)
    for (const link of within(card).getAllByRole('link', { name: 'Check tickets' })) {
      expect(link.getAttribute('rel')).toBe('noopener noreferrer')
      expect(link.getAttribute('referrerpolicy')).toBe('no-referrer')
    }
    fireEvent.click(screen.getByText('Coverage and sources'))
    expect(screen.getByText('Source: CinemaTimes')).toBeTruthy()
  })
  it('shows source uncertainty even when a category has no verified entries', async () => {
    const p = cinemaFixture(); p.films = []; p.returnedShowingCount = 0; p.matchedShowingCount = 0
    state.fetch.mockResolvedValue(p); setup()
    await screen.findByText('No listings returned for this selection')
    fireEvent.change(screen.getByLabelText('Release category'), { target: { value: 'olderFilm' } })
    expect(await screen.findByText('No verified older films found')).toBeTruthy()
    expect(screen.getByText(/Partial coverage:/)).toBeTruthy()
    expect(screen.getByText(/1 screening has an unverified release run/)).toBeTruthy()
  })
  it('removes old-selection actions while a new category is pending and keeps counts before the filter', async () => {
    setup(); await screen.findByRole('article', { name: 'A returning favourite' })
    let complete!: (p: CinemaProgrammeResponse) => void
    state.fetch.mockImplementationOnce(() => new Promise<CinemaProgrammeResponse>(resolve => { complete = resolve }))
    fireEvent.change(screen.getByLabelText('Release category'), { target: { value: 'newRelease' } })
    await waitFor(() => expect(screen.queryAllByRole('link', { name: 'Check tickets' })).toHaveLength(0))
    const p = cinemaFixture(); p.films = [p.films[1]]; p.returnedShowingCount = 1; p.matchedShowingCount = 1; complete(p)
    await screen.findByRole('article', { name: 'A current first run' })
    expect(screen.getByRole('option', { name: 'Older films (2 screenings)' })).toBeTruthy()
  })
  it('suppresses offline and expired cached links without waiting for a fetch', async () => {
    const mounted = setup(); await screen.findByRole('article', { name: 'A returning favourite' })
    state.online = false; mounted.rerender(mounted.tree())
    expect(screen.queryAllByRole('link', { name: 'Check tickets' })).toHaveLength(0)
    expect(screen.getAllByRole('link', { name: 'Official programme' }).length).toBeGreaterThan(0)
  })
  it('removes started showing links when a saved page regains focus without a new response', async () => {
    setup(); await screen.findByRole('article', { name: 'A returning favourite' })
    expect(screen.getAllByRole('link', { name: 'Check tickets' })).toHaveLength(4)
    vi.mocked(Date.now).mockReturnValue(CINEMA_NOW + 8 * 3600000)
    fireEvent.focus(window)
    await waitFor(() => expect(screen.queryAllByRole('link', { name: 'Check tickets' })).toHaveLength(0))
    expect(state.fetch).toHaveBeenCalledTimes(1)
  })
  it('never renders another person’s cached watch status during a profile change', async () => {
    const mounted = setup(); await screen.findByText(/You have watched this/)
    state.fetch.mockImplementationOnce(() => new Promise(() => undefined)); state.id = 'mark'; mounted.rerender(mounted.tree())
    await waitFor(() => expect(screen.queryByText(/You have watched this/)).toBeNull())
    expect(state.fetch).toHaveBeenCalledTimes(2)
  })
  it('retains official fallbacks on first-load failure and explains truncation', async () => {
    state.fetch.mockRejectedValueOnce(new Error('Unavailable')); setup()
    const fallback = await screen.findByRole('region', { name: 'Official cinema programmes' })
    expect(within(fallback).getAllByRole('link')).toHaveLength(9)
    cleanup(); const p = cinemaFixture(); p.truncated = true; state.fetch.mockResolvedValue(p); setup()
    expect(await screen.findByText(/Narrow your date or venue selection/)).toBeTruthy()
  })
  it('rejects inverted dates and an empty venue selection instead of issuing invalid reads', async () => {
    setup(); await screen.findByRole('article', { name: 'A returning favourite' })
    fireEvent.click(screen.getByText('Choose cinemas (2 selected)'))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Vue Glasgow St Enoch' })); await waitFor(() => expect(state.fetch).toHaveBeenCalledTimes(2))
    fireEvent.click(screen.getByRole('checkbox', { name: 'ODEON Kilmarnock' }))
    expect(screen.getByText('Select at least one cinema.')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('From date'), { target: { value: '2026-11-05' } })
    expect(screen.getByText(/Select one to fourteen dates/)).toBeTruthy()
    expect(state.fetch).toHaveBeenCalledTimes(2)
  })
})
