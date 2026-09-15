// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { sinceLabel, WatchHistoryPanel } from './WatchHistoryPanel'

vi.mock('@/lib/api', () => ({
  fetchWatchHistoryStatus: vi.fn(),
  setLetterboxdUsername: vi.fn(),
  syncWatchHistory: vi.fn(),
}))

import { fetchWatchHistoryStatus } from '@/lib/api'

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <WatchHistoryPanel />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)

const RUN = {
  id: 'r1',
  startedAt: new Date(Date.now() - 3 * 86_400_000).toISOString(),
  finishedAt: new Date().toISOString(),
  trigger: 'manual',
  entries: 50,
  written: 4,
  alreadyImported: 46,
  ambiguous: 0,
  notInCollection: 0,
  error: null,
}

describe('sinceLabel', () => {
  const now = Date.parse('2026-09-15T12:00:00Z')

  it('counts in days, because the question is about the gap', () => {
    // The feed holds 50 entries and Mark cycles his in about eight weeks. What a reader
    // needs is how long it has been, not what the calendar said.
    expect(sinceLabel('2026-09-15T09:00:00Z', now)).toBe('today')
    expect(sinceLabel('2026-09-14T09:00:00Z', now)).toBe('yesterday')
    expect(sinceLabel('2026-09-01T12:00:00Z', now)).toBe('14 days ago')
  })

  it('switches to a date once the gap is past the feed window', () => {
    // Beyond eight weeks the count stops being informative — entries have already been
    // lost — so it reads as a date instead of a large and reassuringly precise number.
    expect(sinceLabel('2026-01-01T12:00:00Z', now)).toMatch(/^on /)
  })

  it('does not produce NaN for an unparseable timestamp', () => {
    expect(sinceLabel('not a date', now)).toBe('at an unknown time')
  })
})

describe('WatchHistoryPanel', () => {
  it('says when the sync last ran — the criterion this panel exists for', async () => {
    vi.mocked(fetchWatchHistoryStatus).mockResolvedValue({
      letterboxdUsername: 'CraigR973',
      lastSync: RUN,
      watchCount: 1173,
    })

    renderPanel()

    expect(await screen.findByText('3 days ago')).not.toBeNull()
    expect(screen.getByText(/1,173 watches logged/)).not.toBeNull()
    expect(screen.getByText('CraigR973')).not.toBeNull()
  })

  it('says so plainly when it has never run', async () => {
    vi.mocked(fetchWatchHistoryStatus).mockResolvedValue({
      letterboxdUsername: 'markr973',
      lastSync: null,
      watchCount: 0,
    })

    renderPanel()
    expect(await screen.findByText('Never synced')).not.toBeNull()
  })

  it('shows a failed run as failed rather than as a successful one', async () => {
    // A sync that failed and left no visible trace is indistinguishable from one that
    // never ran, which is the expensive confusion given the 50-entry cap.
    vi.mocked(fetchWatchHistoryStatus).mockResolvedValue({
      letterboxdUsername: 'CraigR973',
      lastSync: { ...RUN, error: 'HTTPStatusError: 503', written: 0 },
      watchCount: 12,
    })

    renderPanel()
    expect(await screen.findByText(/and it failed/)).not.toBeNull()
    expect(screen.getByRole('alert').textContent).toContain('503')
  })

  it('asks for a username before offering a sync that cannot work', async () => {
    vi.mocked(fetchWatchHistoryStatus).mockResolvedValue({
      letterboxdUsername: null,
      lastSync: null,
      watchCount: 0,
    })

    renderPanel()

    await waitFor(() => {
      expect(screen.getByLabelText('Letterboxd username')).not.toBeNull()
    })
    const syncButton = screen.getByRole('button', { name: /sync now/i }) as HTMLButtonElement
    expect(syncButton.disabled).toBe(true)
  })
})
