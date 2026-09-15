// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import CommandPalette from './CommandPalette'

const bladeRunner = {
  id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
  title: 'Blade Runner',
  originalTitle: 'Blade Runner',
  year: 1982,
  posterPath: '/poster.jpg',
  backdropPath: null,
  tmdbRating: 8.1,
  runtimeMinutes: 117,
  bestFormatOwned: '4k_uhd',
  bestHdrOwned: null,
  bestAudioOwned: null,
  identified: true,
  copyCount: 1,
  locations: [],
  watched: false,
}

function LocationProbe({ onChange }: { onChange: (path: string) => void }) {
  onChange(useLocation().pathname)
  return null
}

function renderPalette({ open = true, isAdmin = false } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const onClose = vi.fn()
  let path = ''
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/movies']}>
        <LocationProbe onChange={(p) => { path = p }} />
        <CommandPalette open={open} onClose={onClose} isAdmin={isAdmin} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { onClose, path: () => path }
}

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('CommandPalette', () => {
  it('renders nothing when closed', () => {
    renderPalette({ open: false })
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('lists pages to jump to when the query is empty', () => {
    renderPalette()
    expect(screen.getByText('Movies')).not.toBeNull()
    // Batch S3: 'Stats' was here until the merge, and naming it now would assert a
    // destination that no longer exists. 'Settings' replaces it as the second page —
    // the one the merge created, and the one that was previously in no menu group at all.
    expect(screen.getByText('Settings')).not.toBeNull()
    // And the merged destinations are genuinely gone from the index, not merely renamed.
    expect(screen.queryByText('Stats')).toBeNull()
    expect(screen.queryByText('Insights')).toBeNull()
    // Admin-only actions stay out of a viewer's index, same as the sidebar.
    expect(screen.queryByText('Add a disc')).toBeNull()
  })

  it('includes admin actions in the index for an admin', () => {
    renderPalette({ isAdmin: true })
    expect(screen.getByText('Add a disc')).not.toBeNull()
  })

  it('typing "blade" surfaces Blade Runner and Enter navigates to it', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [bladeRunner],
      query: 'blade',
      total: 1,
    }))))

    const { onClose, path } = renderPalette()
    const input = screen.getByPlaceholderText('Search films, pages, actions…')

    fireEvent.change(input, { target: { value: 'blade' } })
    expect(await screen.findByText('Blade Runner (1982)')).not.toBeNull()

    fireEvent.keyDown(input, { key: 'Enter' })

    expect(path()).toBe(`/movies/${bladeRunner.id}`)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('shows a "no results" state for a query that matches nothing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      items: [],
      query: 'zzzzz',
      total: 0,
    }))))

    renderPalette()
    const input = screen.getByPlaceholderText('Search films, pages, actions…')
    fireEvent.change(input, { target: { value: 'zzzzz' } })

    expect(await screen.findByText('No results for "zzzzz"')).not.toBeNull()
  })

  it('navigates to a page result on click without hitting the search API', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const { onClose, path } = renderPalette()
    // Batch S3 merged Stats into Home, so the palette's page index no longer carries a
    // 'Stats' row. 'Settings' is the destination the merge created, and it exercises the
    // same thing this test is about: a page result navigates without touching search.
    fireEvent.click(screen.getByText('Settings'))

    expect(path()).toBe('/settings')
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('moves the highlighted row with ArrowDown/ArrowUp', () => {
    renderPalette()
    const input = screen.getByPlaceholderText('Search films, pages, actions…')
    const options = () => screen.getAllByRole('option')

    expect(options()[0].getAttribute('aria-selected')).toBe('true')

    fireEvent.keyDown(input, { key: 'ArrowDown' })
    expect(options()[1].getAttribute('aria-selected')).toBe('true')

    fireEvent.keyDown(input, { key: 'ArrowUp' })
    expect(options()[0].getAttribute('aria-selected')).toBe('true')
  })
})
