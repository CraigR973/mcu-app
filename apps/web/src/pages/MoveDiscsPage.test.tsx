// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MoveDiscsPage from './MoveDiscsPage'
import { resetMoveTrayForTests } from '@/hooks/useMoveTray'
import { fetchCopies, moveCollectionItems, type CollectionCopy } from '@/lib/api'
import type { CollectionItem } from '@mcu/shared'

const online = { value: true }
vi.mock('@/hooks/useOnlineStatus', () => ({ useOnlineStatus: () => online.value }))

// The finder is Loans' and has its own tests; here it is a button per film.
vi.mock('@/components/collection/FilmFinder', () => ({
  FilmFinder: ({ onFound }: { onFound: (film: { movieId: string; title: string }) => void }) => (
    <div>
      <button type="button" onClick={() => onFound({ movieId: HEAT, title: 'Heat' })}>Find Heat</button>
      <button type="button" onClick={() => onFound({ movieId: ALIEN, title: 'Alien' })}>Find Alien</button>
    </div>
  ),
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    fetchCopies: vi.fn(),
    moveCollectionItems: vi.fn(),
    fetchFacets: vi.fn().mockResolvedValue({
      sections: [
        { section: 'Back', movieCount: 1, itemCount: 1, shelves: [{ shelf: 'Top', movieCount: 1, itemCount: 1 }] },
        {
          section: 'Lounge',
          movieCount: 1,
          itemCount: 1,
          shelfNoun: 'side',
          shelves: [
            { shelf: 'Left', label: 'Left hand side', movieCount: 0, itemCount: 0 },
            { shelf: 'Right', label: 'Right hand side', movieCount: 1, itemCount: 1 },
          ],
        },
      ],
      unsectionedItemCount: 0,
      decades: [],
      undatedMovieCount: 0,
      discsWithSpecs: 0,
      allSections: ['Front', 'Back', 'Lounge', "Craig's house"],
    }),
  }
})

const HEAT = '3f2504e0-4f89-11d3-9a0c-0305e82c3401'
const ALIEN = '3f2504e0-4f89-11d3-9a0c-0305e82c3402'

function copy(id: string, over: Partial<CollectionCopy> = {}): CollectionCopy {
  return {
    id,
    formats: ['blu_ray'],
    location: 'Front 2nd shelf',
    section: 'Front',
    shelf: '2nd',
    subCategory: null,
    edition: null,
    notes: null,
    purchasePrice: null,
    purchaseSource: null,
    purchaseDate: null,
    condition: null,
    hasPlaybackIssues: false,
    playbackNotes: null,
    videoSpecs: null,
    audioSpecs: null,
    specialFeatures: null,
    regionCode: null,
    releaseLabel: null,
    listingStatus: 'in_collection',
    ebayListingUrl: null,
    listingPrice: null,
    updatedAt: '2026-10-13T09:00:00Z',
    valuation: null,
    ...over,
  }
}

function item(id: string, movieId: string, over: Partial<CollectionItem> = {}): CollectionItem {
  return {
    id,
    movieId,
    movieTitle: 'x',
    formats: ['blu_ray'],
    location: 'Back Top shelf',
    section: 'Back',
    shelf: 'Top',
    locationLabel: 'Back Top',
    subCategory: null,
    edition: null,
    notes: null,
    condition: null,
    conditionUpdatedAt: null,
    hasPlaybackIssues: false,
    playbackNotes: null,
    purchasePrice: null,
    purchaseSource: null,
    purchaseDate: null,
    listingStatus: 'in_collection',
    ebayListingUrl: null,
    listingPrice: null,
    updatedAt: '2026-10-13T12:00:00Z',
    deletedAt: null,
    ...over,
  }
}

const HEAT_DISC = '3f2504e0-4f89-11d3-9a0c-0305e82c3411'
const ALIEN_4K = '3f2504e0-4f89-11d3-9a0c-0305e82c3421'
const ALIEN_DVD = '3f2504e0-4f89-11d3-9a0c-0305e82c3422'

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, networkMode: 'always' }, mutations: { retry: false, networkMode: 'always' } },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <MoveDiscsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  localStorage.clear()
  resetMoveTrayForTests()
  online.value = true
  vi.mocked(fetchCopies).mockImplementation(async (movieId: string) =>
    movieId === HEAT
      ? [copy(HEAT_DISC)]
      : [
          copy(ALIEN_4K, { formats: ['4k_uhd'], section: 'Lounge', shelf: null, location: 'Lounge' }),
          copy(ALIEN_DVD, { formats: ['dvd'] }),
        ],
  )
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Move discs — Batch Y2', () => {
  it('puts a film with one disc straight into the tray, and the tray outlives the page', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Find Heat' }))

    expect(await screen.findByText(/Added Heat \(Blu-ray\) to the tray/)).not.toBeNull()
    expect(screen.getByRole('heading', { name: 'In the tray (1)' })).not.toBeNull()

    cleanup()
    resetMoveTrayForTests()
    renderPage()
    expect(screen.getByRole('heading', { name: 'In the tray (1)' })).not.toBeNull()
  })

  it('asks which disc when a film has several, and adds only the ones picked', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Find Alien' }))

    expect(await screen.findByText('Which discs of Alien?')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /DVD/ }))

    expect(screen.getByRole('button', { name: /DVD/ }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: /4K UHD/ }).getAttribute('aria-pressed')).toBe('false')
    expect(screen.getByRole('heading', { name: 'In the tray (1)' })).not.toBeNull()
  })

  it('moves the tray, reports each disc, keeps a stale one, and moves the rest back', async () => {
    vi.mocked(moveCollectionItems)
      .mockResolvedValueOnce({
        moved: 1,
        results: [
          { itemId: HEAT_DISC, status: 'moved', item: item(HEAT_DISC, HEAT) },
          {
            itemId: ALIEN_DVD,
            status: 'stale',
            item: item(ALIEN_DVD, ALIEN, { section: 'Lounge', shelf: null, location: 'Lounge', updatedAt: '2026-10-13T11:00:00Z' }),
          },
        ],
      })
      .mockResolvedValueOnce({
        moved: 1,
        results: [{ itemId: HEAT_DISC, status: 'moved', item: item(HEAT_DISC, HEAT, { section: 'Front' }) }],
      })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Find Heat' }))
    await screen.findByText(/Added Heat/)
    fireEvent.click(screen.getByRole('button', { name: 'Find Alien' }))
    fireEvent.click(await screen.findByRole('button', { name: /DVD/ }))

    fireEvent.change(screen.getByLabelText('Move to section'), { target: { value: 'Back' } })
    fireEvent.change(screen.getByLabelText('Shelf'), { target: { value: 'Top' } })
    fireEvent.click(screen.getByRole('button', { name: 'Move 2 discs' }))

    await waitFor(() => expect(moveCollectionItems).toHaveBeenCalledTimes(1))
    expect(vi.mocked(moveCollectionItems).mock.calls[0]?.[0]).toEqual([
      { itemId: HEAT_DISC, baseUpdatedAt: '2026-10-13T09:00:00Z', section: 'Back', shelf: 'Top' },
      { itemId: ALIEN_DVD, baseUpdatedAt: '2026-10-13T09:00:00Z', section: 'Back', shelf: 'Top' },
    ])
    expect(await screen.findByRole('heading', { name: '1 disc moved to Back · Top shelf' })).not.toBeNull()
    expect(screen.getByText(/Alien \(DVD\) changed on the other phone and was left where it is, Lounge/)).not.toBeNull()
    // The stale disc stays, at the version the server reported; the moved one leaves.
    expect(screen.getByRole('heading', { name: 'In the tray (1)' })).not.toBeNull()
    expect(screen.getByText(/now Lounge/)).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: /Move them back/ }))
    await waitFor(() => expect(moveCollectionItems).toHaveBeenCalledTimes(2))
    expect(vi.mocked(moveCollectionItems).mock.calls[1]?.[0]).toEqual([
      {
        itemId: HEAT_DISC,
        baseUpdatedAt: '2026-10-13T12:00:00Z',
        location: 'Front 2nd shelf',
        section: 'Front',
        shelf: '2nd',
      },
    ])
    expect(await screen.findByRole('heading', { name: '1 disc put back' })).not.toBeNull()
  })

  it('moves discs to one side of the Lounge, named as a side — Mark, 14 Oct', async () => {
    vi.mocked(moveCollectionItems).mockResolvedValueOnce({
      moved: 1,
      results: [
        {
          itemId: HEAT_DISC,
          status: 'moved',
          item: item(HEAT_DISC, HEAT, {
            section: 'Lounge',
            shelf: 'Right',
            location: 'Lounge Cabinet - Right Hand Side',
            locationLabel: 'Lounge Right',
          }),
        },
      ],
    })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Find Heat' }))
    await screen.findByText(/Added Heat/)

    fireEvent.change(screen.getByLabelText('Move to section'), { target: { value: 'Lounge' } })
    expect(screen.getByRole('option', { name: 'No particular side' })).not.toBeNull()
    fireEvent.change(screen.getByLabelText('Side'), { target: { value: 'Right' } })
    fireEvent.click(screen.getByRole('button', { name: 'Move 1 disc' }))

    await waitFor(() => expect(moveCollectionItems).toHaveBeenCalledTimes(1))
    expect(vi.mocked(moveCollectionItems).mock.calls[0]?.[0]).toEqual([
      { itemId: HEAT_DISC, baseUpdatedAt: '2026-10-13T09:00:00Z', section: 'Lounge', shelf: 'Right' },
    ])
    expect(await screen.findByRole('heading', { name: '1 disc moved to Lounge · Right hand side' })).not.toBeNull()
  })

  it('will not move offline, and says why', async () => {
    online.value = false
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Find Heat' }))
    await screen.findByText(/Added Heat/)
    fireEvent.change(screen.getByLabelText('Move to section'), { target: { value: 'Lounge' } })

    expect(screen.getByRole('button', { name: 'Move 1 disc' }).hasAttribute('disabled')).toBe(true)
    expect(screen.getByText(/Moving needs a connection/)).not.toBeNull()
  })
})
