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
  // Batch X3: the shell reads this person's devices for the stopped-notifications banner.
  fetchPushSubscriptions: vi.fn().mockResolvedValue({ items: [], total: 0, stoppedAt: null }),
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

/** The shell at `path`, or at the last of several paths with the others as its history. */
function renderShell(path: string | string[], page: React.ReactNode = <GoToFilm />) {
  const entries = typeof path === 'string' ? [path] : path
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={entries} initialIndex={entries.length - 1}>
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

  it("focuses the sheet's box while the tap is still being handled — Batch W1, snag 1", () => {
    // iOS raises the keyboard only for a focus made inside the tap's own handling; a focus
    // one animation frame later leaves it down, and Craig's iPhone needed a second tap. A
    // listener on `window` runs at the end of the same click's dispatch, after React's own
    // listener on the root, so what it sees is what iOS judges by.
    renderShell('/movies')
    let focusedDuringTap: Element | null = null
    const onTap = () => {
      focusedDuringTap = document.activeElement
    }
    window.addEventListener('click', onTap)
    fireEvent.click(screen.getByRole('button', { name: 'Search the archive' }))
    window.removeEventListener('click', onTap)

    const sheet = screen.getByRole('dialog', { name: 'Search the archive' })
    const box = within(sheet).getByRole('combobox', { name: 'Search films' })
    expect(focusedDuringTap).toBe(box)
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

  it('gives Wanted, Deals and Settings a back arrow on a phone — Batch V1, snag 5', () => {
    // They are reached from You, so until V1 a phone had no way back from any of them but
    // the initial again. Only the four bottom tabs and You go without one now.
    for (const path of ['/wanted', '/deals', '/settings', '/loans', '/admin']) {
      renderShell(path, <p>A page</p>)
      expect(screen.getByRole('button', { name: 'Back' }), path).not.toBeNull()
      cleanup()
    }
    for (const path of ['/dashboard', '/movies', '/collection/add', '/movie-night', '/you']) {
      renderShell(path, <p>A page</p>)
      expect(screen.queryByRole('button', { name: 'Back' }), path).toBeNull()
      cleanup()
    }
  })

  it('returns to You from a page opened there', async () => {
    renderShell(['/you', '/wanted'], <p>Wanted</p>)
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    await waitFor(() => expect(screen.getByLabelText('Current page').textContent).toBe('/you'))
  })

  it('goes to You from a page You lists when there is no history, as from a notification', async () => {
    renderShell('/deals', <p>Deals</p>)
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    await waitFor(() => expect(screen.getByLabelText('Current page').textContent).toBe('/you'))
  })

  it('returns a film opened from Deals to Deals', async () => {
    renderShell(['/you', '/deals', '/movies/some-film'], <p>A film</p>)
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    await waitFor(() => expect(screen.getByLabelText('Current page').textContent).toBe('/deals'))
  })

  it("is drawn on the bottom bar's surface, not the page's colour — Batch W1, snag 5", () => {
    // Nothing scrolls under the top bar, so the page's colour at any opacity reads as the
    // page itself: that was the "faded" bar. The browser check measures the colours; this
    // keeps the bar from drifting back to them.
    renderShell('/movies/some-film', <p>A film</p>)
    const topBar = screen.getByRole('banner', { name: 'Top bar' })
    const bottomBar = screen.getByRole('navigation', { name: 'Primary mobile navigation' })
    const surface = (element: Element) => element.className.split(/\s+/).find((name) => name.startsWith('bg-'))

    expect(surface(topBar)).toBe('bg-popover')
    expect(surface(bottomBar)?.startsWith('bg-popover')).toBe(true)
    for (const control of [
      within(topBar).getByRole('button', { name: 'Back' }),
      within(topBar).getAllByRole('link', { name: 'Ask the assistant' })[0],
    ]) {
      expect(control.className).not.toMatch(/(^|\s)text-muted-foreground(\s|$)/)
    }
  })

  it('keeps that surface when Search opens over the bar — W1 follow-up', () => {
    // The search sheet is taller than the top bar and covers it, so it *is* the top bar while
    // it is open. It kept the page's colour after W1, and Craig saw the faded bar again each
    // time he tapped Search (dark theme, 5 Oct).
    renderShell('/movies')
    fireEvent.click(screen.getByRole('button', { name: 'Search the archive' }))
    const sheet = screen.getByRole('dialog', { name: 'Search the archive' })
    const surface = sheet.className.split(/\s+/).find((name) => name.startsWith('bg-'))

    expect(surface).toBe('bg-popover')
  })

  it("opens the You page from the person's initial", () => {
    renderShell('/movies')
    const you = screen.getByRole('link', { name: /^You/ })
    expect(you.textContent).toBe('C')
    expect(you.getAttribute('href')).toBe('/you')
  })
})

describe('AppLayout assistant — Batch U3', () => {
  it("puts the assistant in the top bar, beside the person's initial", () => {
    renderShell('/movies')
    const topBar = within(screen.getByRole('banner', { name: 'Top bar' }))

    // Two rows share the top bar, the phone's and the desktop's; CSS shows one of them.
    const links = topBar.getAllByRole('link', { name: 'Ask the assistant' })
    expect(links).toHaveLength(2)
    for (const link of links) expect(link.getAttribute('href')).toBe('/assistant')

    const you = topBar.getByRole('link', { name: /^You/ })
    expect(you.previousElementSibling).toBe(links[0])
  })

  it('has no floating button: the top bar is the only way in from the shell', () => {
    renderShell('/settings')
    const topBar = screen.getByRole('banner', { name: 'Top bar' })

    for (const link of screen.getAllByRole('link', { name: 'Ask the assistant' })) {
      expect(topBar.contains(link)).toBe(true)
      expect(link.className).not.toMatch(/(^|\s)fixed(\s|$)/)
    }
  })

  it('keeps the five bottom tabs five', () => {
    renderShell('/movies')
    const bar = within(screen.getByRole('navigation', { name: 'Primary mobile navigation' }))
    expect([...bar.getAllByRole('link'), ...bar.getAllByRole('button')]).toHaveLength(5)
    expect(bar.queryByRole('link', { name: /assistant/i })).toBeNull()
  })

  it('shows on a movie night, where the floating button had to hide, and marks the chat', () => {
    renderShell('/movie-night/3f2504e0-4f89-41d3-9a0c-0305e82c3401', <p>A night</p>)
    for (const link of screen.getAllByRole('link', { name: 'Ask the assistant' })) {
      expect(link.getAttribute('aria-current')).toBeNull()
    }
    cleanup()

    renderShell('/assistant', <p>The chat</p>)
    for (const link of screen.getAllByRole('link', { name: 'Ask the assistant' })) {
      expect(link.getAttribute('aria-current')).toBe('page')
    }
  })
})

describe('AppLayout sidebar — Batch V1', () => {
  it('lists Loans and Deals with none made yet, while Box sets and Collections still hide', async () => {
    // The mocked counts are all zero, the state that hid Loans from #154 until V1 (#228),
    // and Deals until X2.
    renderShell('/movies')
    const sidebar = within(screen.getByRole('navigation', { name: 'Application destinations' }))
    expect(sidebar.getByRole('link', { name: /Loans/ }).getAttribute('href')).toBe('/loans')
    await waitFor(() => expect(sidebar.queryByRole('link', { name: /Box sets/ })).toBeNull())
    expect(sidebar.queryByRole('link', { name: /Collections/ })).toBeNull()
    expect(sidebar.getByRole('link', { name: /Deals/ }).getAttribute('href')).toBe('/deals')
    expect(sidebar.getByRole('link', { name: /Loans/ })).not.toBeNull()
  })
})
