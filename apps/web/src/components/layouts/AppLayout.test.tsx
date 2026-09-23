// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
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

import { PageHeader } from '@/components/ui/page-header'
import { ThemeProvider } from '@/context/theme'

import AppLayout from './AppLayout'

/** Stands in for picking a search result: it navigates, exactly as `SearchBar` does. */
function GoToFilm() {
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate('/movies/some-film')}>Open a film</button>
}

function Where() {
  return <output aria-label="Current page">{useLocation().pathname}</output>
}

function renderShell(path: string, page: React.ReactNode = <GoToFilm />) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={[path]}>
          <AppLayout>
            <Routes>
              <Route path="*" element={page} />
            </Routes>
            <Where />
          </AppLayout>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
})

describe('AppLayout search sheet', () => {
  it('closes when a pick takes you to the film — Batch T2, snag 6', async () => {
    renderShell('/movies')

    fireEvent.click(screen.getByRole('button', { name: 'Search the archive' }))
    expect(screen.getByRole('dialog', { name: 'Search the archive' })).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Open a film' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Search the archive' })).toBeNull())
  })
})

describe('AppLayout phone top bar — Batch T3', () => {
  it('shows the title the page announced, where the app name used to be', async () => {
    renderShell('/wanted', <PageHeader eyebrow="Wish list" title="Wanted" />)

    // Scoped to the top bar: the page's own heading is in the DOM too, hidden on a phone
    // by a class this test environment does not apply.
    const topBar = within(screen.getByRole('banner', { name: 'Top bar' }))
    expect(await topBar.findByRole('heading', { level: 1, name: 'Wanted' })).not.toBeNull()
    expect(topBar.queryByText('The Real MCU')).toBeNull()
  })

  it('has no menu button any more', () => {
    renderShell('/movies')
    expect(screen.queryByRole('button', { name: 'Open menu' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Open all destinations' })).toBeNull()
  })

  it('gives a page below a destination a back arrow, and a destination none', () => {
    renderShell('/movies')
    expect(screen.queryByRole('button', { name: 'Back' })).toBeNull()
    cleanup()

    renderShell('/movies/some-film', <p>A film</p>)
    expect(screen.getByRole('button', { name: 'Back' })).not.toBeNull()
  })

  it('goes to the parent when there is no history to go back through', async () => {
    renderShell('/movie-night/3f2504e0-4f89-41d3-9a0c-0305e82c3401', <p>A night</p>)

    fireEvent.click(screen.getByRole('button', { name: 'Back' }))

    await waitFor(() => expect(screen.getByLabelText('Current page').textContent).toBe('/movie-night'))
  })

  it("opens the You page from the person's initial", () => {
    renderShell('/movies')
    const you = screen.getByRole('link', { name: /^You/ })
    expect(you.textContent).toBe('C')
    expect(you.getAttribute('href')).toBe('/you')
  })
})
