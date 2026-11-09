// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { updateMock, deleteMock } = vi.hoisted(() => ({ updateMock: vi.fn(), deleteMock: vi.fn() }))

vi.mock('@/lib/sync', () => ({ updateOrQueue: updateMock, deleteOrQueue: deleteMock }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchFacets: vi.fn().mockResolvedValue({ sections: [], allSections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0 }),
}))

import CopyEditor from './CopyEditor'
import type { CollectionCopy } from '@/lib/api'

const MOVIE = 'a1b2c3d4-0000-4000-8000-000000000010'

/** Contagion's Blu-ray copy as it stood on 4 Nov, before Mark ticked 4K UHD on it. */
const BLU_RAY = {
  id: 'c0ffee00-0000-4000-8000-000000000001',
  formats: ['blu_ray'],
  location: 'Front 1st shelf',
  section: 'Front',
  shelf: '1st',
  subCategory: null,
  edition: null,
  notes: null,
  purchasePrice: null,
  purchaseSource: null,
  purchaseDate: null,
  condition: null,
  hasPlaybackIssues: false,
  playbackNotes: null,
  updatedAt: '2026-11-04T21:00:00Z',
} as unknown as CollectionCopy

function Where() {
  const location = useLocation()
  return <p data-testid="where">{`${location.pathname}${location.search}`}</p>
}

function renderEditor(copy: CollectionCopy = BLU_RAY) {
  const onClose = vi.fn()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/movies/${MOVIE}`]}>
        <Routes>
          <Route path="/movies/:id" element={<CopyEditor movieId={MOVIE} copy={copy} isAdmin onClose={onClose} />} />
          <Route path="/collection/add" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { onClose }
}

function tick(format: string) {
  fireEvent.click(screen.getByRole('button', { name: format }))
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('CopyEditor — AE1, one box or a separate copy', () => {
  it('asks before saving when a second disc format is ticked, and saves nothing yet', () => {
    renderEditor()
    tick('4K UHD')
    fireEvent.click(screen.getByRole('button', { name: /Save changes/ }))

    const question = screen.getByRole('alertdialog', { name: 'One box with both discs, or a separate copy?' })
    expect(question.textContent).toContain('One box makes this copy 4K UHD and Blu-ray, a combo pack.')
    expect(question.textContent).toContain('A separate copy leaves this one as Blu-ray and adds the 4K UHD as its own copy.')
    expect(updateMock).not.toHaveBeenCalled()
  })

  it('saves the combo when the answer is one box', async () => {
    updateMock.mockResolvedValue({ item: null, queued: false })
    const { onClose } = renderEditor()
    tick('4K UHD')
    fireEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    fireEvent.click(screen.getByRole('button', { name: /One box with both discs/ }))

    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1))
    const [itemId, movieId, body] = updateMock.mock.calls[0] as [string, string, { formats: string[]; baseUpdatedAt: string }]
    expect([itemId, movieId]).toEqual([BLU_RAY.id, MOVIE])
    expect(body.formats).toEqual(['blu_ray', '4k_uhd'])
    expect(body.baseUpdatedAt).toBe(BLU_RAY.updatedAt)
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('leaves the copy alone and opens Add a copy with the new format when the answer is a separate copy', () => {
    const { onClose } = renderEditor()
    tick('4K UHD')
    fireEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    fireEvent.click(screen.getByRole('button', { name: /A separate copy/ }))

    expect(updateMock).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
    expect(screen.getByTestId('where').textContent).toBe(`/collection/add?movie=${MOVIE}&format=4k_uhd`)
  })

  it('says other changes are not kept by a separate copy, and Back returns to the form', () => {
    renderEditor()
    fireEvent.change(screen.getByRole('textbox', { name: 'Edition' }), { target: { value: 'SteelBook' } })
    tick('4K UHD')
    fireEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    expect(screen.getByText('Your other changes here are not kept if you add a separate copy.')).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    expect(screen.getByRole('button', { name: /Save changes/ })).not.toBeNull()
  })

  it('does not ask when the addition is digital, or when one disc format is swapped for another', async () => {
    updateMock.mockResolvedValue({ item: null, queued: false })
    renderEditor()
    tick('Digital')
    fireEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1))
    expect((updateMock.mock.calls[0]?.[2] as { formats: string[] }).formats).toEqual(['blu_ray', 'download'])

    cleanup()
    updateMock.mockClear()
    renderEditor()
    tick('Blu-ray')
    tick('4K UHD')
    fireEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1))
    expect((updateMock.mock.calls[0]?.[2] as { formats: string[] }).formats).toEqual(['4k_uhd'])
  })

  it('does not ask again about a combo pack that was already one', async () => {
    updateMock.mockResolvedValue({ item: null, queued: false })
    renderEditor({ ...BLU_RAY, formats: ['4k_uhd', 'blu_ray'] })
    fireEvent.change(screen.getByRole('textbox', { name: 'Edition' }), { target: { value: 'SteelBook' } })
    fireEvent.click(screen.getByRole('button', { name: /Save changes/ }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    await waitFor(() => expect(updateMock).toHaveBeenCalledTimes(1))
  })
})
