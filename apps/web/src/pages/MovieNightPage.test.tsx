// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  createMovieNight: vi.fn(),
  endMovieNight: vi.fn(),
  fetchMovieNights: vi.fn(),
  joinMovieNight: vi.fn(),
}))

vi.mock('@/lib/api', () => mocks)

vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: 'p', displayName: 'Craig', role: 'admin', hasPin: true, onboardingCompleted: true } }),
}))

import MovieNightPage from './MovieNightPage'

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/movie-night']}>
        <Routes>
          <Route path="/movie-night" element={<MovieNightPage />} />
          <Route path="/movie-night/:id" element={<p>The night</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('MovieNightPage — Batch V3', () => {
  it('starts a night with "Start movie night", not "Start swiping" (#228)', async () => {
    // A night is its shortlist now, with no deck to swipe.
    mocks.fetchMovieNights.mockResolvedValue({ items: [], total: 0 })
    mocks.createMovieNight.mockResolvedValue({ id: '3f2504e0-4f89-41d3-9a0c-0305e82c3401' })
    renderPage()

    expect(screen.queryByRole('button', { name: /Start swiping/ })).toBeNull()
    fireEvent.click(await screen.findByRole('button', { name: 'Start movie night' }))

    await waitFor(() => expect(mocks.createMovieNight).toHaveBeenCalledWith({}))
    expect(await screen.findByText('The night')).not.toBeNull()
  })
})
