// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: 'p', displayName: 'Craig', role: 'viewer', hasPin: true, onboardingCompleted: true } }),
}))
vi.mock('@/lib/sync', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/sync')>()),
  startAutoFlush: () => () => undefined,
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchNavSections: vi.fn().mockResolvedValue({ boxSets: 0, collections: 0, deals: 0, loans: 0 }),
  fetchSmartCollections: vi.fn().mockResolvedValue({ items: [], total: 0 }),
  fetchSearch: vi.fn().mockResolvedValue({ query: '', total: 0, items: [] }),
  fetchSearchBeyond: vi.fn().mockResolvedValue({ query: '', items: [], unavailable: false }),
}))

import { ThemeProvider } from '@/context/theme'

import AppLayout from './AppLayout'

/** Stands in for picking a search result: it navigates, exactly as `SearchBar` does. */
function GoToFilm() {
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate('/movies/some-film')}>Open a film</button>
}

afterEach(() => {
  cleanup()
})

describe('AppLayout search sheet', () => {
  it('closes when a pick takes you to the film — Batch T2, snag 6', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <ThemeProvider>
          <MemoryRouter initialEntries={['/movies']}>
            <AppLayout>
              <GoToFilm />
            </AppLayout>
          </MemoryRouter>
        </ThemeProvider>
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Search the archive' }))
    expect(screen.getByRole('dialog', { name: 'Search the archive' })).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Open a film' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Search the archive' })).toBeNull())
  })
})
