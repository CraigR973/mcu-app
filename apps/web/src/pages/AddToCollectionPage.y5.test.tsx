// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { searchMock, duplicateMock, confirmMock, addMock } = vi.hoisted(() => ({
  searchMock: vi.fn(),
  duplicateMock: vi.fn(),
  confirmMock: vi.fn(),
  addMock: vi.fn(),
}))

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  searchTmdb: searchMock,
  checkDuplicate: duplicateMock,
  confirmBarcode: confirmMock,
  fetchFacets: vi.fn().mockResolvedValue({ sections: [], allSections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0 }),
}))
vi.mock('@/lib/sync', () => ({ addOrQueue: addMock }))

const BARCODE = '5051892211475'
vi.mock('@/components/collection/BarcodeLookupPanel', () => ({
  default: ({ onManualSearch }: { onManualSearch: (barcode: string) => void }) => (
    <button type="button" onClick={() => onManualSearch(BARCODE)}>
      Simulate manual fallback
    </button>
  ),
}))

import AddToCollectionPage from './AddToCollectionPage'

const MOVIE = '00000000-0000-4000-8000-000000000071'

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <AddToCollectionPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function search(words: string) {
  fireEvent.change(screen.getByRole('textbox', { name: 'Search for a film' }), { target: { value: words } })
  fireEvent.click(screen.getByRole('button', { name: /^Search$/ }))
}

/** The form starts on Blu-ray, which is what these discs are. */
function addAsBluRay(title: string) {
  fireEvent.click(screen.getByRole('button', { name: `Add “${title}”` }))
}

beforeEach(() => {
  searchMock.mockResolvedValue({
    query: 'Life',
    results: [
      { tmdbId: 395992, title: 'Life', year: 2017, overview: 'A sample from Mars.', posterPath: null, inCollection: false, movieId: null },
    ],
    series: [
      { tmdbId: 3797, title: 'Life', year: 2007, overview: 'A detective back from prison.', posterPath: null, inCollection: false, movieId: null, mediaType: 'tv' },
      { tmdbId: 16946, title: 'Life', year: 2009, overview: 'David Attenborough on survival.', posterPath: null, inCollection: false, movieId: null, mediaType: 'tv' },
    ],
  })
  duplicateMock.mockResolvedValue({ isDuplicate: false, existingCopies: [], isUpgrade: false, bestFormatOwned: null })
  addMock.mockResolvedValue({ item: { movieId: MOVIE }, queued: false })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AddToCollectionPage — Batch Y5', () => {
  it('lists TMDB’s series apart from the films and adds a disc to one by its series id', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Search title' }))
    search('Life')

    const series = await screen.findByRole('list', { name: 'TV series found' })
    expect(within(screen.getByRole('list', { name: 'Films found' })).getAllByRole('listitem')).toHaveLength(1)
    expect(within(series).getAllByText('TV series')).toHaveLength(2)
    fireEvent.click(within(series).getByRole('button', { name: /2009/ }))

    await waitFor(() => expect(duplicateMock).toHaveBeenCalledWith({ tmdbTvId: 16946 }, ['blu_ray']))
    addAsBluRay('Life')
    await waitFor(() => expect(addMock).toHaveBeenCalled())
    const body = addMock.mock.calls[0]?.[0] as Record<string, unknown>
    expect(body.tmdbTvId).toBe(16946)
    expect(body.tmdbId).toBeUndefined()
    expect(body.formats).toEqual(['blu_ray'])
  })

  it('adds a disc TMDB does not have by its title', async () => {
    searchMock.mockResolvedValue({ query: 'A Day in the Life', results: [], series: [] })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Search title' }))
    search('A Day in the Life')

    expect(await screen.findByText('No films or series matched “A Day in the Life”.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Add “A Day in the Life” by its title' }))
    await waitFor(() => expect(duplicateMock).toHaveBeenCalledWith({ title: 'A Day in the Life' }, ['blu_ray']))
    addAsBluRay('A Day in the Life')

    await waitFor(() => expect(addMock).toHaveBeenCalled())
    const body = addMock.mock.calls[0]?.[0] as Record<string, unknown>
    expect(body.title).toBe('A Day in the Life')
    expect(body.tmdbId).toBeUndefined()
    expect(body.movieId).toBeUndefined()
  })

  it('skips the barcode confirmation for a series, keeping the barcode on the copy', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Simulate manual fallback' }))
    search('Life')

    const series = await screen.findByRole('list', { name: 'TV series found' })
    fireEvent.click(within(series).getByRole('button', { name: /2009/ }))
    addAsBluRay('Life')

    await waitFor(() => expect(addMock).toHaveBeenCalled())
    expect(confirmMock).not.toHaveBeenCalled()
    const body = addMock.mock.calls[0]?.[0] as Record<string, unknown>
    expect(body.barcode).toBe(BARCODE)
    expect(body.tmdbTvId).toBe(16946)
  })

  it('reads an answer from before Y5, which has no series', async () => {
    searchMock.mockResolvedValue({
      query: 'Gilda',
      results: [{ tmdbId: 3767, title: 'Gilda', year: 1946, overview: '', posterPath: null, inCollection: false, movieId: null }],
    })
    renderPage()
    fireEvent.click(screen.getByRole('tab', { name: 'Search title' }))
    search('Gilda')

    expect(await screen.findByRole('list', { name: 'Films found' })).toBeTruthy()
    expect(screen.queryByRole('list', { name: 'TV series found' })).toBeNull()
  })
})
