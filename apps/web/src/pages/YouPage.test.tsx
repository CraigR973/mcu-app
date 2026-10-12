// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const state = vi.hoisted(() => ({
  role: 'viewer' as 'viewer' | 'admin',
  signOut: vi.fn(),
  sections: { boxSets: 1, collections: 1, deals: 1, loans: 1 },
}))
vi.mock('@/context/auth', () => ({
  useAuth: () => ({
    profile: { id: 'p', displayName: 'Mark', role: state.role, hasPin: true, onboardingCompleted: true },
    signOut: state.signOut,
  }),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchNavSections: vi.fn(() => Promise.resolve(state.sections)),
  fetchSmartCollections: vi.fn().mockResolvedValue({ items: [], total: 0 }),
}))

import { ThemeProvider } from '@/context/theme'
import { adminNavItems, BOTTOM_BAR_PATHS, navItems } from '@/lib/nav-items'

import YouPage from './YouPage'

function renderYou() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <MemoryRouter initialEntries={['/you']}>
          <YouPage />
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

function linkedPaths(): Set<string> {
  return new Set(screen.getAllByRole('link').map((link) => link.getAttribute('href') ?? ''))
}

beforeEach(() => {
  state.role = 'viewer'
  state.signOut.mockReset()
  state.sections = { boxSets: 1, collections: 1, deals: 1, loans: 1 }
})

afterEach(() => {
  cleanup()
})

describe('YouPage — Batch T3', () => {
  it('reaches every destination the bottom bar does not, for an admin', async () => {
    state.role = 'admin'
    renderYou()
    await screen.findByRole('link', { name: /Box sets/ })

    const onPage = linkedPaths()
    const inBar = new Set<string>(BOTTOM_BAR_PATHS)
    for (const item of [...navItems, ...adminNavItems]) {
      expect(inBar.has(item.path) || onPage.has(item.path), `${item.label} (${item.path})`).toBe(true)
    }
  })

  it('does not repeat what the bottom bar already has', async () => {
    renderYou()
    await screen.findByRole('link', { name: /Wanted/ })
    const onPage = linkedPaths()
    for (const path of BOTTOM_BAR_PATHS) expect(onPage.has(path), path).toBe(false)
  })

  it('hides a destination while its table is empty', async () => {
    state.sections = { boxSets: 0, collections: 0, deals: 0, loans: 0 }
    renderYou()
    await screen.findByRole('link', { name: /Wanted/ })
    await waitFor(() => expect(screen.queryByRole('link', { name: /Box sets/ })).toBeNull())
    expect(screen.queryByRole('link', { name: /Collections/ })).toBeNull()
    // Batch X2: Deals stays, its empty page saying when each source last answered.
    expect(screen.getByRole('link', { name: /Deals/ }).getAttribute('href')).toBe('/deals')
  })

  it('lists Loans with no loan made yet, for Mark as for Craig — Batch V1 (#228)', async () => {
    // Loans hid with the other three until V1 (#154); Craig asked for it always, for both.
    state.sections = { boxSets: 0, collections: 0, deals: 0, loans: 0 }
    for (const role of ['viewer', 'admin'] as const) {
      state.role = role
      renderYou()
      await screen.findByRole('link', { name: /Wanted/ })
      await waitFor(() => expect(screen.queryByRole('link', { name: /Box sets/ })).toBeNull())
      expect(screen.getByRole('link', { name: /Loans/ }).getAttribute('href'), role).toBe('/loans')
      cleanup()
    }
  })

  it('shows the admin pages to an admin only', async () => {
    renderYou()
    await screen.findByRole('link', { name: /Wanted/ })
    expect(screen.queryByRole('link', { name: /Audit log/ })).toBeNull()
  })

  it('signs out', async () => {
    renderYou()
    fireEvent.click(await screen.findByRole('button', { name: /Sign out/ }))
    expect(state.signOut).toHaveBeenCalledOnce()
  })
})
