// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { CompletionSet } from '@mcu/shared'

const auth = vi.hoisted(() => ({ role: 'admin' as 'admin' | 'viewer' }))
const api = vi.hoisted(() => ({ fetchCompletionInsights: vi.fn(), excludeCompletionFilm: vi.fn(), addWanted: vi.fn() }))

vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: 'p1', displayName: 'Craig', role: auth.role } }),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))

import { CompletionShelf } from './CompletionShelf'

const film = (tmdbId: number, title: string, year: number, wanted = false) => ({ tmdbId, title, year, posterPath: null, owned: false, movieId: null, wanted, counts: true })

function set(id: string, name: string, owned: number, total: number, missingFilms: CompletionSet['missingFilms']): CompletionSet {
  return {
    id,
    setType: 'director',
    setKey: name,
    setName: name,
    ownedCount: owned,
    totalCount: total,
    missingCount: total - owned,
    percentComplete: Math.floor((owned * 100) / total),
    lastRefreshed: null,
    personProfilePath: null,
    excludedCount: 0,
    missingFilms,
  }
}

// Live data on 8 Nov: Eastwood 39 of 40, Kubrick 12 of 13, Hitchcock 48 of 54.
const EASTWOOD = set('3f2504e0-4f89-41d3-9a0c-0305e82c3701', 'Clint Eastwood', 39, 40, [film(54321, 'Piano Blues', 2003)])
const KUBRICK = set('3f2504e0-4f89-41d3-9a0c-0305e82c3702', 'Stanley Kubrick', 12, 13, [film(12345, 'Fear and Desire', 1953, true)])
const HITCHCOCK = set('3f2504e0-4f89-41d3-9a0c-0305e82c3703', 'Alfred Hitchcock', 48, 54, [
  film(2753, 'The Mountain Eagle', 1926),
  film(2754, 'The Pleasure Garden', 1925),
  film(2755, 'Downhill', 1927),
])

function renderShelf(onOpen = vi.fn()) {
  api.fetchCompletionInsights.mockResolvedValue({ items: [EASTWOOD, KUBRICK, HITCHCOCK], total: 3, oldestRefresh: null })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CompletionShelf onOpen={onOpen} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { onOpen, client }
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  auth.role = 'admin'
})

describe('Closest to complete on Home — AE3 (#355, point 3)', () => {
  it('names what each set is missing, up to three, with +N more opening the set', async () => {
    const { onOpen } = renderShelf()
    const hitchcock = within(await screen.findByRole('list', { name: 'Missing from Alfred Hitchcock' }))
    expect(hitchcock.getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      expect.stringContaining('The Mountain Eagle (1926)'),
      expect.stringContaining('The Pleasure Garden (1925)'),
      expect.stringContaining('Downhill (1927)'),
    ])
    fireEvent.click(screen.getByRole('button', { name: '+3 more' }))
    expect(onOpen).toHaveBeenCalledWith(HITCHCOCK.id)
    // Eastwood's one missing film is named, so there is nothing more to open.
    expect(screen.queryByRole('button', { name: '+0 more' })).toBeNull()
  })

  it('offers Craig Want through the existing Wanted path, and reads Wanted for one already wanted', async () => {
    api.addWanted.mockResolvedValue({})
    renderShelf()
    const eastwood = within(await screen.findByRole('list', { name: 'Missing from Clint Eastwood' }))
    fireEvent.click(eastwood.getByRole('button', { name: 'Want' }))
    await waitFor(() => expect(api.addWanted).toHaveBeenCalledWith({ tmdbId: 54321 }))
    const kubrick = within(screen.getByRole('list', { name: 'Missing from Stanley Kubrick' }))
    expect(kubrick.getByText('Wanted')).not.toBeNull()
    expect(kubrick.queryByRole('button', { name: 'Want' })).toBeNull()
  })

  it('gives Mark "Doesn’t count" but not Want, as Wanted is Craig’s to add to', async () => {
    auth.role = 'viewer'
    api.excludeCompletionFilm.mockResolvedValue({ ...EASTWOOD, films: [] })
    const { client } = renderShelf()
    const eastwood = within(await screen.findByRole('list', { name: 'Missing from Clint Eastwood' }))
    expect(eastwood.queryByRole('button', { name: 'Want' })).toBeNull()
    const refreshed = vi.spyOn(client, 'invalidateQueries')
    fireEvent.click(eastwood.getByRole('button', { name: /Doesn’t count/ }))
    await waitFor(() => expect(api.excludeCompletionFilm).toHaveBeenCalledWith(EASTWOOD.id, 54321))
    // The row reads again, so a set now complete leaves it.
    await waitFor(() => expect(refreshed).toHaveBeenCalledWith({ queryKey: ['completion-insights'] }))
  })

  it('says so when it cannot be saved', async () => {
    api.excludeCompletionFilm.mockRejectedValue(new Error('The archive had a problem.'))
    renderShelf()
    const eastwood = within(await screen.findByRole('list', { name: 'Missing from Clint Eastwood' }))
    fireEvent.click(eastwood.getByRole('button', { name: /Doesn’t count/ }))
    expect(await eastwood.findByRole('alert')).not.toBeNull()
  })
})
