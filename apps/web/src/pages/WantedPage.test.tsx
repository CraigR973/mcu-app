// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import WantedPage from './WantedPage'

vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { role: 'admin' } }),
}))

const MOVIE_ID = '3f2504e0-4f89-11d3-9a0c-0305e82c3301'
const WANTED_ID = '3f2504e0-4f89-11d3-9a0c-0305e82c3302'


/** One wanted film with every buying preference set — so a wipe is visible. */
const EXISTING = {
  id: WANTED_ID,
  movieId: MOVIE_ID,
  movieTitle: 'The Fall Guy',
  year: 2024,
  posterPath: '/fall-guy.jpg',
  preferredFormat: '4k_uhd',
  preferredEdition: 'Steelbook',
  maxPrice: '20',
  currency: 'GBP',
  isActive: true,
  notes: null,
  ownedAlready: false,
  addedAt: '2026-09-09T12:00:00Z',
}

/** Lists `EXISTING`, and answers any PUT with the same row so the call can be inspected. */
function listThenCapture() {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'PUT') {
      return new Response(JSON.stringify(EXISTING))
    }
    if (String(input).includes('/wanted')) {
      return new Response(JSON.stringify({ items: [EXISTING], total: 1, activeCount: 1 }))
    }
    return new Response(JSON.stringify({ items: [], total: 0, activeCount: 0 }))
  })
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <WantedPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('WantedPage', () => {
  it('lets an admin search for one film and add it with buying preferences', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.includes('/tmdb/search')) {
        return new Response(JSON.stringify({
          query: 'The Fall Guy',
          results: [{
            tmdbId: 746036,
            title: 'The Fall Guy',
            year: 2024,
            overview: 'A stuntman searches for a missing star.',
            posterPath: '/fall-guy.jpg',
            inCollection: false,
            movieId: null,
          }],
        }))
      }
      if (url.endsWith('/wanted') && init?.method === 'POST') {
        return new Response(JSON.stringify({
          id: WANTED_ID,
          movieId: MOVIE_ID,
          movieTitle: 'The Fall Guy',
          year: 2024,
          posterPath: '/fall-guy.jpg',
          preferredFormat: '4k_uhd',
          preferredEdition: 'Steelbook',
          maxPrice: '20',
          currency: 'GBP',
          isActive: true,
          notes: null,
          ownedAlready: false,
          addedAt: '2026-09-09T12:00:00Z',
        }), { status: 201 })
      }
      return new Response(JSON.stringify({ items: [], total: 0, activeCount: 0 }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPage()

    fireEvent.change(screen.getByLabelText('Search for a wanted film'), {
      target: { value: 'The Fall Guy' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByText('The Fall Guy')).not.toBeNull()

    fireEvent.change(screen.getByLabelText('Preferred format'), {
      target: { value: '4k_uhd' },
    })
    fireEvent.change(screen.getByLabelText('Preferred edition'), {
      target: { value: 'Steelbook' },
    })
    fireEvent.change(screen.getByLabelText('Maximum price in pounds'), {
      target: { value: '20' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
      expect(post).toBeDefined()
      expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({
        tmdbId: 746036,
        preferredFormat: '4k_uhd',
        preferredEdition: 'Steelbook',
        maxPrice: '20',
      })
    })
  })

  /**
   * `PUT /wanted/{id}` replaces the row, and every field on its request model defaults to
   * `null`. Sending `{ isActive }` alone wiped the format, edition, maximum price and
   * notes on every press of "Stop looking" — silently, in production. `DECISIONS.md` #123.
   */
  it('keeps the buying preferences when an admin stops looking for a film', async () => {
    const fetchMock = listThenCapture()
    vi.stubGlobal('fetch', fetchMock)
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Stop looking' }))

    await waitFor(() => {
      const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
      expect(put).toBeDefined()
      expect(JSON.parse(String(put?.[1]?.body))).toEqual({
        preferredFormat: '4k_uhd',
        preferredEdition: 'Steelbook',
        maxPrice: '20',
        currency: 'GBP',
        isActive: false,
        notes: null,
      })
    })
  })

  it('lets an admin set a maximum price on a film already on the list', async () => {
    const fetchMock = listThenCapture()
    vi.stubGlobal('fetch', fetchMock)
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Set a maximum price for The Fall Guy' }))
    fireEvent.change(screen.getByLabelText('Maximum price for The Fall Guy'), {
      target: { value: '14' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
      expect(put).toBeDefined()
      // The new limit, and everything else exactly as it was.
      expect(JSON.parse(String(put?.[1]?.body))).toEqual({
        preferredFormat: '4k_uhd',
        preferredEdition: 'Steelbook',
        maxPrice: '14',
        currency: 'GBP',
        isActive: true,
        notes: null,
      })
    })
  })

  it('clears the limit when the field is emptied, rather than sending an empty string', async () => {
    const fetchMock = listThenCapture()
    vi.stubGlobal('fetch', fetchMock)
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Set a maximum price for The Fall Guy' }))
    fireEvent.change(screen.getByLabelText('Maximum price for The Fall Guy'), {
      target: { value: '  ' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))

    await waitFor(() => {
      const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')
      expect(JSON.parse(String(put?.[1]?.body)).maxPrice).toBeNull()
    })
  })
})
