// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { duplicateMock, addMock, movieMock } = vi.hoisted(() => ({
  duplicateMock: vi.fn(),
  addMock: vi.fn(),
  movieMock: vi.fn(),
}))

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  checkDuplicate: duplicateMock,
  fetchMovie: movieMock,
  fetchFacets: vi.fn().mockResolvedValue({ sections: [], allSections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0 }),
}))
vi.mock('@/lib/sync', () => ({ addOrQueue: addMock }))
vi.mock('@/components/collection/BarcodeLookupPanel', () => ({
  default: ({
    onBarcodeChange,
    onConfirmed,
  }: {
    onBarcodeChange: (barcode: string | null) => void
    onConfirmed: (candidate: unknown, barcode: string) => Promise<void>
  }) => (
    <button
      type="button"
      onClick={() => {
        onBarcodeChange('5021866000000')
        void onConfirmed(
          { title: 'Contagion', source: 'collection', confidence: 1, movieId: '00000000-0000-4000-8000-0000000000c0', tmdbId: null, year: 2011, posterPath: null, evidence: null },
          '5021866000000',
        )
      }}
    >
      Simulate a scan of the same film
    </button>
  ),
}))

import AddToCollectionPage from './AddToCollectionPage'

const MOVIE = '00000000-0000-4000-8000-0000000000c0'

/** Contagion holds a Blu-ray copy; the new box is a 4K. */
const OWNS_BLU_RAY = {
  isDuplicate: true,
  isUpgrade: true,
  bestFormatOwned: 'blu_ray',
  existingCopies: [{ id: 'copy-1', formats: ['blu_ray'], locationLabel: 'Front 1st shelf' }],
  barcodeCopy: null,
  maybeOwned: null,
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AddToCollectionPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  movieMock.mockResolvedValue({ id: MOVIE, title: 'Contagion', year: 2011, posterPath: null })
  duplicateMock.mockResolvedValue(OWNS_BLU_RAY)
  addMock.mockResolvedValue({ item: { movieId: MOVIE }, queued: false })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('AddToCollectionPage — AE1, a separate copy', () => {
  it('opens on the film and format the address names, and asks the check about that format', async () => {
    renderAt(`/collection/add?movie=${MOVIE}&format=4k_uhd`)

    expect(await screen.findByText('A new copy of this film.')).not.toBeNull()
    expect(screen.getByText('Contagion')).not.toBeNull()
    // The finder stays beneath it, so the new box can still be scanned or another film chosen.
    expect(screen.getByRole('tablist', { name: 'How to find the film' })).not.toBeNull()
    expect(movieMock).toHaveBeenCalledWith(MOVIE)
    expect(screen.getByRole('button', { name: '4K UHD' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: 'Blu-ray' }).getAttribute('aria-pressed')).toBe('false')
    await waitFor(() =>
      expect(duplicateMock).toHaveBeenCalledWith({ movieId: MOVIE }, ['4k_uhd'], { barcode: null, title: 'Contagion', year: 2011 }),
    )
    // The prompt keeps its meaning: an upgrade, or a second box on the shelf.
    expect(await screen.findByText('You already own this on Blu-ray')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'This is an upgrade' })).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Add as a separate copy/ }))

    await waitFor(() => expect(addMock).toHaveBeenCalledTimes(1))
    const body = addMock.mock.calls[0]?.[0] as Record<string, unknown>
    expect(body.movieId).toBe(MOVIE)
    expect(body.formats).toEqual(['4k_uhd'])
    expect(body.confirmDuplicate).toBe('another_copy')
  })

  it('ignores a format the address makes up', async () => {
    renderAt(`/collection/add?movie=${MOVIE}&format=laserdisc`)
    expect(await screen.findByText('A new copy of this film.')).not.toBeNull()
    expect(screen.getByText('Choose the format of this copy.')).not.toBeNull()
  })

  it('asks the check again when the format changes, so a 4K reads as an upgrade', async () => {
    duplicateMock.mockImplementation((_film: unknown, formats: string[]) =>
      Promise.resolve({ ...OWNS_BLU_RAY, isUpgrade: formats.includes('4k_uhd') }),
    )
    renderAt(`/collection/add?movie=${MOVIE}`)
    expect(await screen.findByText('This film is already in the collection')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'This is an upgrade' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '4K UHD' }))
    expect(await screen.findByRole('button', { name: 'This is an upgrade' })).not.toBeNull()
    expect(duplicateMock).toHaveBeenLastCalledWith({ movieId: MOVIE }, ['4k_uhd'], expect.anything())
  })

  it('will not add a copy with no format, and says to choose one', async () => {
    duplicateMock.mockResolvedValue({ ...OWNS_BLU_RAY, isDuplicate: false, existingCopies: [] })
    renderAt(`/collection/add?movie=${MOVIE}`)
    const add = await screen.findByRole('button', { name: 'Add “Contagion”' })
    expect(add.hasAttribute('disabled')).toBe(false)

    fireEvent.click(add)
    expect(screen.getByRole('alert').textContent).toBe('Choose a format: 4K UHD, Blu-ray, DVD or Digital.')
    expect(addMock).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'DVD' }))
    expect(screen.queryByRole('alert')).toBeNull()
    fireEvent.click(add)
    await waitFor(() => expect(addMock).toHaveBeenCalledTimes(1))
    expect((addMock.mock.calls[0]?.[0] as Record<string, unknown>).formats).toEqual(['dvd'])
  })

  it('says so when the film cannot be loaded, and leaves the finder to find it', async () => {
    movieMock.mockRejectedValue(new Error('offline'))
    renderAt(`/collection/add?movie=${MOVIE}&format=4k_uhd`)
    fireEvent.click(await screen.findByRole('button', { name: 'Find it below instead' }))
    expect(screen.queryByRole('button', { name: 'Find it below instead' })).toBeNull()
    expect(screen.getByRole('tablist', { name: 'How to find the film' })).not.toBeNull()
  })

  it('switches to the film a scanned box names, and keeps the barcode for the copy', async () => {
    renderAt(`/collection/add?movie=${MOVIE}&format=4k_uhd`)
    expect(await screen.findByText('A new copy of this film.')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Simulate a scan of the same film' }))
    expect(await screen.findByRole('button', { name: 'Add “Contagion”' })).not.toBeNull()
    expect(screen.queryByText('A new copy of this film.')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Add as a separate copy/ }))
    await waitFor(() => expect(addMock).toHaveBeenCalledTimes(1))
    const body = addMock.mock.calls[0]?.[0] as Record<string, unknown>
    expect([body.movieId, body.barcode, body.formats]).toEqual([MOVIE, '5021866000000', ['4k_uhd']])
  })
})
