// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CompletionSetDetail } from '@mcu/shared'

const auth = vi.hoisted(() => ({ role: 'viewer' as 'admin' | 'viewer' }))
const { fetchCompletionSetMock, addWantedMock, excludeMock, countAgainMock } = vi.hoisted(() => ({
  fetchCompletionSetMock: vi.fn(),
  addWantedMock: vi.fn(),
  excludeMock: vi.fn(),
  countAgainMock: vi.fn(),
}))

vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: 'p1', displayName: 'Craig', role: auth.role } }),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  addWanted: addWantedMock,
  fetchCompletionSet: fetchCompletionSetMock,
  excludeCompletionFilm: excludeMock,
  countCompletionFilmAgain: countAgainMock,
}))

import { CompletionSetPanel } from './CompletionSetPanel'

const SET: CompletionSetDetail = {
  id: '3f2504e0-4f89-41d3-9a0c-0305e82c3601',
  setType: 'director',
  setKey: '2636',
  setName: 'Alfred Hitchcock',
  ownedCount: 1,
  totalCount: 2,
  missingCount: 1,
  percentComplete: 50,
  lastRefreshed: '2026-10-24T10:00:00Z',
  personProfilePath: '/hitchcock.jpg',
  excludedCount: 0,
  missingFilms: [],
  films: [
    { tmdbId: 539, title: 'Psycho', year: 1960, posterPath: '/psycho.jpg', owned: false, movieId: null, wanted: true, counts: true },
    { tmdbId: 426, title: 'Vertigo', year: 1958, posterPath: '/vertigo.jpg', owned: true, movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3602', wanted: false, counts: true },
  ],
}

function renderPanel(set = SET) {
  fetchCompletionSetMock.mockResolvedValue(set)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CompletionSetPanel setId={SET.id} onBack={() => undefined} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  auth.role = 'viewer'
})

describe('CompletionSetPanel — AA2', () => {
  it('separates missing films, links each one to TMDB, and shows the shared Wanted status to Mark', async () => {
    renderPanel()

    const missing = within(await screen.findByRole('region', { name: 'Missing films' }))
    expect(missing.getByText('Psycho')).not.toBeNull()
    expect(missing.getByRole('link', { name: /TMDB/ }).getAttribute('href')).toBe('https://www.themoviedb.org/movie/539')
    expect(missing.getByText('Wanted')).not.toBeNull()
    expect(within(screen.getByRole('region', { name: 'On the shelf' })).getByText('Vertigo')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Add to Wanted' })).toBeNull()
  })

  it('offers Craig an individual add action for a missing film that is not wanted', async () => {
    auth.role = 'admin'
    renderPanel({
      ...SET,
      films: [{ ...SET.films[0], wanted: false }, SET.films[1]],
    })

    fireEvent.click(await screen.findByRole('button', { name: 'Add to Wanted' }))
    await waitFor(() => expect(addWantedMock).toHaveBeenCalledWith({ tmdbId: 539 }))
  })
})

describe('CompletionSetPanel — AE3, a film that does not count (#355, point 3)', () => {
  const MOUNTAIN_EAGLE = { tmdbId: 2753, title: 'The Mountain Eagle', year: 1926, posterPath: null, owned: false, movieId: null, wanted: false, counts: false }

  it('lets either person say a missing film does not count, in this set', async () => {
    excludeMock.mockResolvedValue(SET)
    renderPanel()
    const missing = within(await screen.findByRole('region', { name: 'Missing films' }))
    fireEvent.click(missing.getByRole('button', { name: /Doesn’t count/ }))
    await waitFor(() => expect(excludeMock).toHaveBeenCalledWith(SET.id, 539))
  })

  it('lists what does not count apart, struck through, with Count it again', async () => {
    countAgainMock.mockResolvedValue(SET)
    renderPanel({ ...SET, excludedCount: 1, films: [...SET.films, MOUNTAIN_EAGLE] })

    const notCounted = within(await screen.findByRole('region', { name: 'Not counted' }))
    const title = notCounted.getByText('The Mountain Eagle (1926)')
    expect(title.className).toContain('line-through')
    expect(within(screen.getByRole('region', { name: 'Missing films' })).queryByText('The Mountain Eagle')).toBeNull()
    expect(screen.getByText(/1 not counted/)).not.toBeNull()
    fireEvent.click(notCounted.getByRole('button', { name: /Count it again/ }))
    await waitFor(() => expect(countAgainMock).toHaveBeenCalledWith(SET.id, 2753))
  })

  it('leaves films that do not count out of Add all missing to Wanted', async () => {
    auth.role = 'admin'
    renderPanel({ ...SET, films: [{ ...SET.films[0], wanted: false }, SET.films[1], MOUNTAIN_EAGLE] })
    expect(await screen.findByRole('button', { name: /Add 1 missing to wanted/ })).not.toBeNull()
  })
})
