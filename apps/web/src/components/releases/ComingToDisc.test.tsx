// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { fetchCalendarMock } = vi.hoisted(() => ({ fetchCalendarMock: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchCalendar: fetchCalendarMock,
}))

import { ComingToDisc } from './ComingToDisc'

function entry(id: number, title: string, releaseDate: string, releaseType: string) {
  return {
    id: `00000000-0000-4000-8000-${String(id).padStart(12, '0')}`,
    title,
    releaseType,
    typeLabel: releaseType === '4k_uhd_release' ? '4K UHD' : releaseType === 'blu_ray_release' ? 'Blu-ray' : 'In cinemas',
    releaseDate,
    label: null,
    region: 'GB',
    url: null,
    posterPath: null,
    overview: null,
    movieId: null,
  }
}

function renderIt(limit?: number) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ComingToDisc limit={limit} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  fetchCalendarMock.mockReset().mockResolvedValue({
    total: 4,
    refreshedAt: new Date(Date.now() - 2 * 3_600_000).toISOString(),
    items: [
      entry(1, 'Frankenstein', '2026-10-26', '4k_uhd_release'),
      entry(2, 'A Cinema Release', '2026-10-27', 'theatrical'),
      entry(3, 'KPop Demon Hunters', '2026-11-09', 'blu_ray_release'),
      entry(4, '28 Days Later', '2026-11-16', '4k_uhd_release'),
    ],
  })
})

afterEach(() => {
  cleanup()
})

describe('ComingToDisc — Batch T5', () => {
  it('lists the next disc releases from today, by month, and leaves out cinema dates', async () => {
    renderIt()

    expect(await screen.findByText('Frankenstein')).not.toBeNull()
    expect(screen.getByText('October 2026')).not.toBeNull()
    expect(screen.getByText('November 2026')).not.toBeNull()
    expect(screen.queryByText('A Cinema Release')).toBeNull()
    // Asked of the upcoming list — six months — not of whichever month the calendar shows.
    expect(fetchCalendarMock).toHaveBeenCalledWith(183)
  })

  it('says how fresh it is, and that TMDB will be missing some', async () => {
    renderIt()
    expect(await screen.findByText(/Updated from TMDB 2 hours ago/)).not.toBeNull()
    expect(screen.getByText(/some releases\s+will be missing/)).not.toBeNull()
  })

  it("is Home's short list when limited, with a way to the rest", async () => {
    renderIt(2)
    const section = within(await screen.findByRole('region', { name: /Coming to disc/ }))
    expect(section.getAllByRole('listitem')).toHaveLength(2)
    expect(section.getByRole('link', { name: 'All releases' }).getAttribute('href')).toBe('/calendar')
  })

  it('hides itself on Home when nothing is coming', async () => {
    fetchCalendarMock.mockResolvedValue({ total: 0, refreshedAt: null, items: [] })
    renderIt(5)
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.queryByRole('region', { name: /Coming to disc/ })).toBeNull()
  })
})
