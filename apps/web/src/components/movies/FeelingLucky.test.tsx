// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { MovieListItem } from '@/lib/api'

const api = vi.hoisted(() => ({ dealLuckyFilm: vi.fn(), suggestMovieNightFilm: vi.fn() }))
const auth = vi.hoisted(() => ({ id: 'craig' }))
vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { id: auth.id } }) }))
vi.mock('@/lib/api', async (original) => ({ ...(await original<typeof import('@/lib/api')>()), ...api }))
import { FeelingLucky } from './FeelingLucky'

const film = (id: string, title: string): MovieListItem => ({
  id, title, originalTitle: null, year: 1994, posterPath: null, backdropPath: null,
  tmdbRating: 8, runtimeMinutes: 100, bestFormatOwned: 'bluray', bestHdrOwned: null,
  bestAudioOwned: null, identified: true, setAsideAs: null, mediaType: 'film', copyCount: 1,
  locations: [{ section: 'Front', shelf: '2nd', label: 'Front 2nd' }], watched: false,
  lastWatchedAt: null, editions: [],
})
const A = film('a', 'First film')
const B = film('b', 'Second film')
function setup(sessionId?: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const ui = (night = sessionId) => <QueryClientProvider client={client}><MemoryRouter><FeelingLucky sessionId={night} /></MemoryRouter></QueryClientProvider>
  return { ...render(ui()), ui, client }
}
beforeEach(() => { api.dealLuckyFilm.mockReset(); api.suggestMovieNightFilm.mockReset(); auth.id = 'craig'; api.suggestMovieNightFilm.mockResolvedValue({ items: [] }) })
afterEach(cleanup)

describe('Feeling lucky', () => {
  it('deals lazily, limits Home to my unwatched films, excludes every dealt film, and ends on exhaustion', async () => {
    api.dealLuckyFilm.mockResolvedValueOnce({ film: A }).mockResolvedValueOnce({ film: B }).mockResolvedValueOnce({ film: null })
    setup()
    expect(api.dealLuckyFilm).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: 'Deal a film' }))
    await screen.findByRole('heading', { name: A.title })
    expect(api.dealLuckyFilm).toHaveBeenNthCalledWith(1, { excludedIds: [], unwatchedOnly: true, sessionId: undefined })
    expect((screen.getByRole('checkbox') as HTMLInputElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Skip this film' }))
    await screen.findByRole('heading', { name: B.title })
    expect(api.dealLuckyFilm).toHaveBeenNthCalledWith(2, { excludedIds: ['a'], unwatchedOnly: true, sessionId: undefined })
    fireEvent.click(screen.getByRole('button', { name: 'Skip this film' }))
    await screen.findByText(/No more films for this run/)
    expect(api.dealLuckyFilm).toHaveBeenNthCalledWith(3, { excludedIds: ['a', 'b'], unwatchedOnly: true, sessionId: undefined })
    expect(screen.queryByRole('button', { name: 'Choose this film' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Start again' }))
    expect((screen.getByRole('checkbox') as HTMLInputElement).disabled).toBe(false)
    api.dealLuckyFilm.mockResolvedValue({ film: A })
    fireEvent.click(screen.getByRole('button', { name: 'Deal a film' }))
    await screen.findByRole('heading', { name: A.title })
    expect(api.dealLuckyFilm).toHaveBeenLastCalledWith({ excludedIds: [], unwatchedOnly: true, sessionId: undefined })
  })

  it('confirms a solo pick without suggesting it or logging a watch', async () => {
    api.dealLuckyFilm.mockResolvedValue({ film: A })
    setup()
    fireEvent.click(screen.getByRole('button', { name: 'Deal a film' }))
    await screen.findByRole('heading', { name: A.title })
    fireEvent.click(screen.getByRole('button', { name: 'Choose this film' }))
    await screen.findByText(`Your pick: ${A.title}.`)
    expect(screen.getByRole('link', { name: 'Open film' }).getAttribute('href')).toBe('/movies/a')
    expect(api.suggestMovieNightFilm).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Skip this film' })).toBeNull()
  })

  it('only adds to a night when chosen and refreshes its shortlist', async () => {
    api.dealLuckyFilm.mockResolvedValue({ film: A })
    const { client } = setup('night-one')
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    expect(screen.queryByRole('checkbox')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Deal a film' }))
    await screen.findByRole('heading', { name: A.title })
    expect(api.suggestMovieNightFilm).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Choose this film' }))
    await screen.findByText(/Added “First film” to tonight’s suggestions/)
    expect(api.suggestMovieNightFilm).toHaveBeenCalledTimes(1)
    expect(api.suggestMovieNightFilm).toHaveBeenCalledWith('night-one', { movieId: 'a' })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['movie-night-candidates', 'night-one'] })
  })

  it('keeps the current film and all exclusions on a failed skip or choose', async () => {
    api.dealLuckyFilm.mockResolvedValueOnce({ film: A }).mockRejectedValueOnce(new Error('Network down')).mockResolvedValueOnce({ film: B })
    api.suggestMovieNightFilm.mockRejectedValueOnce(new Error('Night ended'))
    setup('night-one')
    fireEvent.click(screen.getByRole('button', { name: 'Deal a film' }))
    await screen.findByRole('heading', { name: A.title })
    fireEvent.click(screen.getByRole('button', { name: 'Choose this film' }))
    await screen.findByRole('alert')
    expect(screen.getByRole('heading', { name: A.title })).not.toBeNull()
    expect(screen.queryByText(/Added “/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Skip this film' }))
    await screen.findByRole('button', { name: 'Try again' })
    expect(screen.getByRole('heading', { name: A.title })).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await screen.findByRole('heading', { name: B.title })
    expect(api.dealLuckyFilm).toHaveBeenLastCalledWith({ excludedIds: ['a'], unwatchedOnly: false, sessionId: 'night-one' })
  })

  it('prevents another deal and choosing while the next film is arriving', async () => {
    let resolve!: (value: { film: MovieListItem }) => void
    api.dealLuckyFilm.mockImplementation(() => new Promise((done) => { resolve = done }))
    setup()
    fireEvent.click(screen.getByRole('button', { name: 'Deal a film' }))
    await waitFor(() => expect((screen.getByRole('button', { name: 'Dealing…' }) as HTMLButtonElement).disabled).toBe(true))
    expect((screen.getByRole('button', { name: 'Start again' }) as HTMLButtonElement).disabled).toBe(true)
    resolve({ film: A })
    await screen.findByRole('heading', { name: A.title })
  })

  it('clears the old run on account or night change', async () => {
    api.dealLuckyFilm.mockResolvedValue({ film: A })
    const view = setup('night-one')
    fireEvent.click(screen.getByRole('button', { name: 'Deal a film' }))
    await screen.findByRole('heading', { name: A.title })
    auth.id = 'mark'
    view.rerender(view.ui('night-one'))
    expect(screen.queryByRole('heading', { name: A.title })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Deal a film' }))
    await screen.findByRole('heading', { name: A.title })
    expect(api.dealLuckyFilm).toHaveBeenLastCalledWith({ excludedIds: [], unwatchedOnly: false, sessionId: 'night-one' })
    view.rerender(view.ui('night-two'))
    expect(within(screen.getByRole('group', { name: 'Feeling lucky' })).queryByRole('heading', { name: A.title })).toBeNull()
    expect((screen.getByRole('button', { name: 'Deal a film' }) as HTMLButtonElement).disabled).toBe(false)
  })
})
