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
})
