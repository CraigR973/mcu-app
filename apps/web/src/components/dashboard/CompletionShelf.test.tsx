// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
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

describe('Closest to complete on Home — AE3 (#355, point 3), tidied by AF2 (#372)', () => {
  it('names what each set is missing, up to three, with +N for the rest, in one block that opens the set', async () => {
    const { onOpen } = renderShelf()
    const hitchcock = await screen.findByRole('button', { name: /Alfred Hitchcock/ })
    expect(hitchcock.textContent).toContain('Missing: The Mountain Eagle (1926), The Pleasure Garden (1925), Downhill (1927)')
    expect(within(hitchcock).getByText('+3')).not.toBeNull()
    fireEvent.click(hitchcock)
    expect(onOpen).toHaveBeenCalledWith(HITCHCOCK.id)
    // Eastwood's one missing film is named, so there is no "+N".
    const eastwood = screen.getByRole('button', { name: /Clint Eastwood/ })
    expect(eastwood.textContent).toContain('Missing: Piano Blues (2003)')
    expect(eastwood.textContent).not.toMatch(/\+\d/)
  })

  it('has no buttons inside a set for Craig or Mark: Want and Doesn’t count are on its page', async () => {
    for (const role of ['admin', 'viewer'] as const) {
      auth.role = role
      renderShelf()
      const section = within((await screen.findByRole('heading', { name: 'Closest to complete' })).closest('section') as HTMLElement)
      // One button per set, and nothing else to press.
      expect(section.getAllByRole('button')).toHaveLength(3)
      expect(section.queryByRole('button', { name: 'Want' })).toBeNull()
      expect(section.queryByRole('button', { name: /Doesn’t count/ })).toBeNull()
      expect(api.addWanted).not.toHaveBeenCalled()
      expect(api.excludeCompletionFilm).not.toHaveBeenCalled()
      cleanup()
    }
  })

  it('names no films for a set whose answer names none, as an older API sends', async () => {
    api.fetchCompletionInsights.mockResolvedValue({ items: [{ ...HITCHCOCK, missingFilms: [] }], total: 1, oldestRefresh: null })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <CompletionShelf onOpen={vi.fn()} />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const hitchcock = await screen.findByRole('button', { name: /Alfred Hitchcock/ })
    expect(hitchcock.textContent).toContain('6 missing')
    expect(hitchcock.textContent).not.toContain('Missing:')
  })
})
