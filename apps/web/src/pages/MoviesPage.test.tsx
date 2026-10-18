// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ fetchMovies: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchMovies: mocks.fetchMovies,
}))
// The three views and the filter bar have their own tests; what is under test is what the page
// asks for and when it shows it.
vi.mock('@/components/movies/FilterBar', () => ({ FilterBar: () => null }))
vi.mock('@/components/movies/MovieListView', () => ({ MovieListView: () => null }))
vi.mock('@/components/movies/MovieCompactView', () => ({ MovieCompactView: () => null }))
vi.mock('@/components/movies/MovieGrid', () => ({
  MovieGrid: ({ movies, isLoading }: { movies: unknown[]; isLoading: boolean }) => (
    <p data-testid="grid">{isLoading ? 'loading' : `${String(movies.length)} films`}</p>
  ),
}))
vi.mock('@/hooks/useViewPreference', () => ({
  useViewPreference: () => ({
    viewMode: 'grid',
    setViewMode: vi.fn(),
    enabledColumns: [],
    toggleColumn: vi.fn(),
  }),
}))

import MoviesPage from './MoviesPage'

function page(count: number, total: number) {
  return {
    items: Array.from({ length: count }, (_, index) => ({ id: String(index), title: `Film ${String(index)}` })),
    totalMovies: total,
    totalItems: total,
    page: 1,
    perPage: count,
    pages: 1,
  }
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MoviesPage />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mocks.fetchMovies.mockReset()
})
afterEach(() => {
  cleanup()
})

describe('MoviesPage — the first screen before the rest (Batch X12b, UX48-07)', () => {
  it('shows the first 60 films while the full list is still on its way, then all of them', async () => {
    let release: (value: unknown) => void = () => undefined
    mocks.fetchMovies.mockImplementation((_filters: unknown, _page: number, perPage: number) =>
      perPage === 60 ? Promise.resolve(page(60, 1900)) : new Promise((resolve) => (release = resolve)),
    )
    renderPage()

    expect(await screen.findByText('60 films')).not.toBeNull()
    expect(screen.getByRole('status').textContent).toContain('Showing the first 60 of 1900 films')
    expect(mocks.fetchMovies).toHaveBeenCalledWith(expect.anything(), 1, 60)
    expect(mocks.fetchMovies).toHaveBeenCalledWith(expect.anything(), 1, 2000)

    release(page(1900, 1900))
    expect(await screen.findByText('1900 films')).not.toBeNull()
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull())
  })

  it('keeps the first screen and says so when the rest cannot be loaded', async () => {
    // The first screen's query is declared first, so it is asked first.
    mocks.fetchMovies
      .mockResolvedValueOnce(page(60, 1900))
      .mockRejectedValueOnce(new Error('down'))
    renderPage()

    expect(await screen.findByText('60 films')).not.toBeNull()
    expect((await screen.findByRole('status')).textContent).toContain('the rest could not be loaded')
    expect(screen.queryByText('The archive could not be opened')).toBeNull()
  })

  it('says the archive could not be opened when not even the first screen arrives', async () => {
    mocks.fetchMovies
      .mockRejectedValueOnce(new Error('down'))
      .mockRejectedValueOnce(new Error('down'))
    renderPage()

    expect(await screen.findByText('The archive could not be opened')).not.toBeNull()
  })

  it('shows a short list at once, with no "loading the rest" line', async () => {
    mocks.fetchMovies.mockImplementation((_filters: unknown, _page: number, perPage: number) =>
      Promise.resolve(perPage === 60 ? page(12, 12) : page(12, 12)),
    )
    renderPage()

    expect(await screen.findByText('12 films')).not.toBeNull()
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull())
  })
})
