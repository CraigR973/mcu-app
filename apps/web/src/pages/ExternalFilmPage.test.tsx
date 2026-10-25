// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  fetchExternalFilm: vi.fn(),
  fetchMovieNights: vi.fn(),
  addWanted: vi.fn(),
  suggestMovieNightFilm: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...mocks,
}))

import ExternalFilmPage from './ExternalFilmPage'

const FILM = {
  tmdbId: 11050, title: 'The Card Player', year: 2004, posterPath: null, backdropPath: null,
  overview: 'A film nobody here owns.', runtimeMinutes: 103, genres: ['Thriller'],
  cast: ['Top Billed'], directors: ['Dario Argento'], movieId: null, owned: false,
  wanted: false, region: 'GB', link: 'https://www.themoviedb.org/movie/11050/watch?locale=GB',
  offers: [
    { providerId: 8, providerName: 'Netflix', logoPath: null, kind: 'flatrate' },
    { providerId: 2, providerName: 'Apple TV', logoPath: null, kind: 'rent' },
  ],
}

const NIGHT = {
  id: '3f2504e0-4f89-41d3-9a0c-0305e82c3401', status: 'open', filters: {},
  inviteToken: 'token', invitePath: '/movie-night/join/token', participantCount: 2,
  createdAt: '2026-09-23T18:00:00Z', endedAt: null,
}

function Where() {
  return <output aria-label="Current page">{useLocation().pathname}</output>
}

function renderCard(state?: unknown) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: '/films/tmdb/11050', state }]}>
        <Routes>
          <Route path="/films/tmdb/:tmdbId" element={<ExternalFilmPage />} />
          <Route path="*" element={null} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mocks.fetchExternalFilm.mockReset().mockResolvedValue(FILM)
  mocks.fetchMovieNights.mockReset().mockResolvedValue({ items: [], total: 0 })
  mocks.addWanted.mockReset().mockResolvedValue({})
  mocks.suggestMovieNightFilm.mockReset().mockResolvedValue({ items: [], total: 0 })
})

afterEach(() => {
  cleanup()
})

describe('ExternalFilmPage', () => {
  it('describes a film nobody here owns, and where to watch it', async () => {
    renderCard()

    expect(await screen.findByRole('heading', { name: 'The Card Player' })).not.toBeNull()
    expect(screen.getByText('Netflix')).not.toBeNull()
    expect(screen.getByText('Apple TV')).not.toBeNull()
    expect(screen.getByRole('link', { name: /Prices and links on TMDB/ }).getAttribute('href')).toBe(FILM.link)
    expect(mocks.fetchExternalFilm).toHaveBeenCalledWith(11050)
  })

  it('adds it to Wanted by its TMDB id', async () => {
    renderCard()
    fireEvent.click(await screen.findByRole('button', { name: /Add to Wanted/ }))

    await waitFor(() => expect(mocks.addWanted).toHaveBeenCalledWith({ tmdbId: 11050 }))
  })

  it('offers it to an open movie night, and goes there', async () => {
    mocks.fetchMovieNights.mockResolvedValue({ items: [NIGHT], total: 1 })
    renderCard()
    fireEvent.click(await screen.findByRole('button', { name: /Add to movie night/ }))

    await waitFor(() =>
      expect(mocks.suggestMovieNightFilm).toHaveBeenCalledWith(NIGHT.id, {
        tmdbId: 11050, title: 'The Card Player', year: 2004, posterPath: null,
      }),
    )
    await waitFor(() => expect(screen.getByLabelText('Current page').textContent).toBe(`/movie-night/${NIGHT.id}`))
  })

  it('does not offer a movie night when none is open', async () => {
    renderCard()
    await screen.findByRole('heading', { name: 'The Card Player' })

    expect(screen.queryByRole('button', { name: /Add to movie night/ })).toBeNull()
  })

  it('sends an owned film to its own page instead', async () => {
    mocks.fetchExternalFilm.mockResolvedValue({ ...FILM, owned: true, movieId: '11111111-1111-4111-8111-111111111111' })
    renderCard()

    await waitFor(() =>
      expect(screen.getByLabelText('Current page').textContent).toBe('/movies/11111111-1111-4111-8111-111111111111'),
    )
  })

  it('points at the shelf copy it might be', async () => {
    renderCard({ maybeOwned: { movieId: '44444444-4444-4444-8444-444444444444', title: 'Card Player, The' } })

    expect(await screen.findByText(/might be your copy of “Card Player, The”/)).not.toBeNull()
    expect(screen.getByRole('link', { name: 'Open it' }).getAttribute('href')).toBe('/movies/44444444-4444-4444-8444-444444444444')
  })
})
