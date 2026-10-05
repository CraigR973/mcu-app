// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompletionSet, Stats } from '@mcu/shared'

import type { CalendarEntry, CollectionValue, Highlights } from '@/lib/api'

const auth = vi.hoisted(() => ({ role: 'admin' as 'admin' | 'viewer' }))
vi.mock('@/context/auth', () => ({
  useAuth: () => ({
    profile: { id: 'p', displayName: 'Craig', role: auth.role, hasPin: true, onboardingCompleted: true },
  }),
}))

const api = vi.hoisted(() => ({
  fetchStats: vi.fn(),
  fetchCollectionValue: vi.fn(),
  fetchCalendar: vi.fn(),
  fetchHighlights: vi.fn(),
  fetchOnThisDayMemories: vi.fn(),
  fetchRewatchSuggestions: vi.fn(),
  fetchCompletionInsights: vi.fn(),
  fetchCompletionSet: vi.fn(),
  fetchSmartCollections: vi.fn(),
  fetchActivity: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))

import DashboardPage from './DashboardPage'

const HEAT = '3f2504e0-4f89-41d3-9a0c-0305e82c3401'
const ALIEN = '3f2504e0-4f89-41d3-9a0c-0305e82c3402'

const STATS: Stats = {
  totalMovies: 1888,
  totalItems: 1880,
  identifiedMovies: 1678,
  watchedMovies: 594,
  formats: [{ key: 'bluray', label: 'Blu-ray', itemCount: 900, movieCount: 880 }],
  genres: [{ key: 'drama', label: 'Drama', itemCount: 700, movieCount: 690 }],
  decades: [{ decade: 1990, label: '1990s', movieCount: 300 }],
  sections: [{ key: 'Front', label: 'Front', itemCount: 400, movieCount: 390 }],
  mostWatched: [{ movieId: HEAT, title: 'Heat', posterPath: null, watchCount: 4, lastWatched: '2026-09-01' }],
  spendOverTime: [],
  itemsWithPrice: 0,
}

const VALUE: CollectionValue = {
  total: '1903.34',
  currency: 'GBP',
  basis: 'current asking prices',
  discs: 1880,
  pricedDiscs: 1454,
  notPricedDiscs: 300,
  uncheckedDiscs: 126,
  checkedFrom: '2026-09-24T03:00:00Z',
  checkedTo: '2026-09-25T03:00:00Z',
  due: 0,
  budgetLeft: 750,
  dailyShare: 750,
  minSample: 3,
  run: null,
}

const RELEASE: CalendarEntry = {
  id: '3f2504e0-4f89-41d3-9a0c-0305e82c3501',
  title: 'Blood Simple',
  releaseType: '4k_uhd_release',
  typeLabel: '4K',
  releaseDate: '2026-10-20',
  label: null,
  region: 'GB',
  url: null,
  posterPath: null,
  overview: null,
  movieId: HEAT,
}

const HIGHLIGHTS: Highlights = {
  topRated: { items: [{ movieId: HEAT, title: 'Heat', year: 1995, posterPath: null, ratings: [{ personName: 'Craig', rating: 5 }] }], ratedBy: ['Craig'], notRatedBy: ['Mark'] },
  mostRewatched: [{ movieId: ALIEN, title: 'Alien', year: 1979, posterPath: null, viewings: 3, byPerson: [{ personName: 'Craig', viewings: 3 }] }],
  mostValuable: [
    { movieId: HEAT, title: 'Heat', year: 1995, posterPath: null, formatCode: '4k_uhd', price: '34.99', currency: 'GBP', basis: 'current asking prices', sampleSize: 7, checkedAt: '2026-09-26T03:00:00Z', copies: 1 },
  ],
  bestReviewed: [{ movieId: ALIEN, title: 'Alien', year: 1979, posterPath: null, overall: 4.5, outOf: 5, formatCode: '4k_uhd' }],
}

function set(id: string, name: string, owned: number, total: number): CompletionSet {
  return {
    id,
    setType: 'director',
    setKey: name.toLowerCase(),
    setName: name,
    ownedCount: owned,
    totalCount: total,
    missingCount: total - owned,
    percentComplete: Math.floor((owned / total) * 100),
    lastRefreshed: '2026-09-20T00:00:00Z',
  }
}
const SETS = [
  set('3f2504e0-4f89-41d3-9a0c-0305e82c3601', 'Bess Flowers', 18, 353),
  set('3f2504e0-4f89-41d3-9a0c-0305e82c3602', 'Michael Mann', 10, 11),
  set('3f2504e0-4f89-41d3-9a0c-0305e82c3603', 'John Carpenter', 15, 19),
]

/** Everything with something in it, for both people unless a test says otherwise. */
function fill() {
  api.fetchStats.mockResolvedValue(STATS)
  api.fetchCollectionValue.mockResolvedValue(VALUE)
  api.fetchCalendar.mockResolvedValue({ items: [RELEASE], total: 1, refreshedAt: null })
  api.fetchHighlights.mockResolvedValue(HIGHLIGHTS)
  api.fetchOnThisDayMemories.mockResolvedValue([
    { id: '3f2504e0-4f89-41d3-9a0c-0305e82c3701', movieId: HEAT, movieTitle: 'Heat', posterPath: null, watchedAt: '2024-10-05', yearsAgo: 2, personalRating: null },
  ])
  api.fetchRewatchSuggestions.mockResolvedValue([
    { movieId: ALIEN, movieTitle: 'Alien', posterPath: null, lastWatchedAt: '2025-01-12', personalRating: 4.5 },
  ])
  api.fetchCompletionInsights.mockResolvedValue({ items: SETS, total: SETS.length, oldestRefresh: null })
  api.fetchSmartCollections.mockResolvedValue({ items: [], total: 0 })
  api.fetchActivity.mockResolvedValue({ items: [] })
}

function renderHome() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/dashboard']}>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** The sections' headings, top to bottom. */
function headings(): string[] {
  return screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent?.trim() ?? '')
}

beforeEach(() => {
  auth.role = 'admin'
  fill()
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Home as rows, the collection first — Batch W2', () => {
  it('runs the collection first, then disc releases, the highlights, memories, completion and activity', async () => {
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Completion' })
    await screen.findByRole('heading', { level: 2, name: 'Coming to disc' })
    expect(headings()).toEqual([
      'The collection',
      'Coming to disc',
      'Top rated',
      'Most rewatched',
      'Most valuable discs',
      'Best reviewed',
      'On this day',
      'Worth a rewatch',
      'Completion',
      'Recent activity',
    ])
  })

  it('makes every section but Recent activity a row that scrolls sideways', async () => {
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Completion' })
    for (const heading of screen.getAllByRole('heading', { level: 2 })) {
      const section = heading.closest('section')
      expect(section, heading.textContent ?? '').not.toBeNull()
      const rows = [...(section as HTMLElement).querySelectorAll('ul')].filter((list) =>
        list.className.split(/\s+/).includes('overflow-x-auto'),
      )
      if (heading.textContent?.includes('Recent activity')) expect(rows).toHaveLength(0)
      else expect(rows.length, heading.textContent ?? '').toBeGreaterThan(0)
    }
  })

  it('has no Add a disc, no Most watched, and no valuation or bid-trial controls, even for an admin', async () => {
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Completion' })
    expect(screen.queryByRole('link', { name: /Add a disc/ })).toBeNull()
    expect(screen.queryByText('Most watched')).toBeNull()
    expect(screen.queryByRole('button', { name: /Update values|Value the collection|Try bid prices/ })).toBeNull()
    expect(screen.queryByRole('heading', { name: /Bid prices/ })).toBeNull()
  })

  it("shows the collection's worth in the numbers, priced discs counted", async () => {
    renderHome()
    const numbers = within(await screen.findByRole('list', { name: 'The collection in numbers' }))
    expect(await numbers.findByText('≈ £1,903')).not.toBeNull()
    expect(numbers.getByText('1,454 of 1,880 discs priced')).not.toBeNull()
    expect(numbers.getByText('1,888')).not.toBeNull()
  })

  it('leaves the worth out for a viewer until there is a total', async () => {
    auth.role = 'viewer'
    api.fetchCollectionValue.mockResolvedValue({ ...VALUE, total: null, pricedDiscs: 0 })
    renderHome()
    const numbers = within(await screen.findByRole('list', { name: 'The collection in numbers' }))
    await waitFor(() => expect(api.fetchCollectionValue).toHaveBeenCalled())
    expect(numbers.queryByText('Worth')).toBeNull()
  })

  it('hides a row with nothing in it', async () => {
    api.fetchOnThisDayMemories.mockResolvedValue([])
    api.fetchCalendar.mockResolvedValue({ items: [], total: 0, refreshedAt: null })
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Completion' })
    expect(headings()).not.toContain('On this day')
    expect(headings()).not.toContain('Coming to disc')
  })

  it('puts the sets closest to complete first, and links to all of them', async () => {
    renderHome()
    const heading = await screen.findByRole('heading', { level: 2, name: 'Completion' })
    const section = within(heading.closest('section') as HTMLElement)
    const names = section.getAllByRole('button').map((button) => button.querySelector('span')?.textContent)
    expect(names).toEqual(['Michael Mann', 'John Carpenter', 'Bess Flowers'])
    expect(section.getByRole('link', { name: 'All 3' }).getAttribute('href')).toBe('/insights')
  })

  it('opens the set tapped, not the list — the bug W2 found', async () => {
    api.fetchCompletionSet.mockResolvedValue({ ...SETS[1], films: [] })
    renderHome()
    const heading = await screen.findByRole('heading', { level: 2, name: 'Completion' })
    fireEvent.click(within(heading.closest('section') as HTMLElement).getByText('Michael Mann'))

    await waitFor(() => expect(api.fetchCompletionSet).toHaveBeenCalledWith(SETS[1].id))
    expect(screen.queryByRole('heading', { level: 2, name: 'The collection' })).toBeNull()

    // Its back control names where it goes, and goes there.
    fireEvent.click(screen.getByRole('button', { name: 'Home' }))
    expect(await screen.findByRole('heading', { level: 2, name: 'The collection' })).not.toBeNull()
  })
})
