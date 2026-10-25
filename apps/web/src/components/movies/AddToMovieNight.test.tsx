// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { AddToMovieNight } from './AddToMovieNight'

const mocks = vi.hoisted(() => ({ fetchMovieNights: vi.fn(), suggestMovieNightFilm: vi.fn() }))
vi.mock('@/lib/api', () => mocks)
afterEach(() => { cleanup(); vi.clearAllMocks() })
function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><Routes><Route path="/" element={<AddToMovieNight movieId="film" />} /><Route path="/movie-night/:id" element={<p>Opened the night</p>} /></Routes></MemoryRouter>
  </QueryClientProvider>)
}
it('lets the person choose between open nights and adds the owned film to that night', async () => {
  mocks.fetchMovieNights.mockResolvedValue({ items: [
    { id: 'one', status: 'open', createdAt: '2026-10-25T18:00:00Z', plannedStart: null },
    { id: 'two', status: 'open', createdAt: '2026-10-25T19:00:00Z', plannedStart: '2026-11-01T20:00:00Z' },
    { id: 'ended', status: 'ended', createdAt: '2026-10-25T17:00:00Z' },
  ] })
  mocks.suggestMovieNightFilm.mockResolvedValue({ items: [], total: 0 })
  show()
  fireEvent.change(await screen.findByRole('combobox', { name: 'Which movie night' }), { target: { value: 'two' } })
  expect(screen.getAllByRole('option')).toHaveLength(2)
  fireEvent.click(screen.getByRole('button', { name: 'Add to movie night' }))
  await waitFor(() => expect(mocks.suggestMovieNightFilm).toHaveBeenCalledWith('two', { movieId: 'film' }))
  expect(await screen.findByText('Opened the night')).not.toBeNull()
})
it('offers no action when all nights have ended', async () => {
  mocks.fetchMovieNights.mockResolvedValue({ items: [{ id: 'one', status: 'ended' }] })
  show()
  await waitFor(() => expect(mocks.fetchMovieNights).toHaveBeenCalled())
  expect(screen.queryByRole('button', { name: 'Add to movie night' })).toBeNull()
})
