// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { LendButton } from './LendButton'
import { PhotoGallery } from './PhotoGallery'
import WatchPanel from '@/components/movies/WatchPanel'
import { fetchItemPhotos, fetchLoans, fetchWatches } from '@/lib/api'

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    fetchItemPhotos: vi.fn(),
    fetchLoans: vi.fn(),
    fetchWatches: vi.fn(),
  }
})

const MOVIE_ID = '3f2504e0-4f89-11d3-9a0c-0305e82c3301'
const ITEM_ID = '3f2504e0-4f89-11d3-9a0c-0305e82c3302'
const PHOTO_ID = '3f2504e0-4f89-11d3-9a0c-0305e82c3303'

function renderWithClient(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, networkMode: 'always' },
      mutations: { retry: false, networkMode: 'always' },
    },
  })
  render(<QueryClientProvider client={client}>{children}</QueryClientProvider>)
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('detail subcomponent query states', () => {
  it('does not turn a watch-log failure into an unwatched claim', async () => {
    vi.mocked(fetchWatches).mockRejectedValueOnce(new Error('Watch log unavailable'))
    renderWithClient(<WatchPanel movieId={MOVIE_ID} />)

    expect(await screen.findByText('Could not load your watch history')).not.toBeNull()
    expect(screen.getByText('Watch log unavailable')).not.toBeNull()
    expect(screen.queryByText('No watches logged')).toBeNull()
    expect((screen.getByRole('button', { name: 'Mark watched' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('does not offer to lend a disc when its active-loan lookup failed', async () => {
    vi.mocked(fetchLoans).mockRejectedValueOnce(new Error('Loan status unavailable'))
    renderWithClient(<LendButton collectionItemId={ITEM_ID} />)

    expect(await screen.findByText('Loan status unavailable')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Lend' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Try again' })).not.toBeNull()
  })

  it('does not present a failed photo request as an empty gallery or a full quota', async () => {
    vi.mocked(fetchItemPhotos).mockRejectedValueOnce(new Error('Photos unavailable'))
    renderWithClient(<PhotoGallery itemId={ITEM_ID} canEdit />)

    expect(await screen.findByText('Photos unavailable')).not.toBeNull()
    expect(screen.queryByText('No photos of this disc yet.')).toBeNull()
    expect(screen.queryByText('Five is the limit')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Take a photo' })).toBeNull()
  })

  it('opens a labelled, keyboard-dismissible photo dialog', async () => {
    vi.mocked(fetchItemPhotos).mockResolvedValueOnce({
      items: [{
        id: PHOTO_ID,
        url: '/photos/slipcover.jpg',
        caption: 'Slipcover',
        width: 1200,
        height: 1600,
        byteSize: 250000,
        position: 0,
        createdAt: '2026-09-09T10:00:00Z',
      }],
      total: 1,
      remaining: 4,
    })
    renderWithClient(<PhotoGallery itemId={ITEM_ID} canEdit={false} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Open photo: Slipcover' }))
    expect(screen.getByRole('dialog', { name: 'Disc photo: Slipcover' })).not.toBeNull()

    fireEvent.keyDown(document, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  })
})
