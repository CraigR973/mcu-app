// @vitest-environment happy-dom
import { onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
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
  // Batch X2: Home's "Needs attention" row, for the admin. Nothing wrong here.
  fetchAttention: vi.fn().mockResolvedValue({ items: [], checkedAt: null }),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))
vi.mock('@/components/brand/PrivateHero', () => ({
  PrivateHero: ({ hero, alt }: { hero: string; alt: string }) => <img data-testid="private-hero" data-hero={hero} alt={alt} />,
}))

import DashboardPage from './DashboardPage'

const HEAT = '3f2504e0-4f89-41d3-9a0c-0305e82c3401'
const ALIEN = '3f2504e0-4f89-41d3-9a0c-0305e82c3402'

const STATS: Stats = {
  totalMovies: 1888,
  totalItems: 1880,
  downloadCopies: 422,
  physicalCopies: 1880,
  physicalAndDownloadCopies: 422,
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
  valuedAs: 'as used copies',
  discs: 1880,
  pricedDiscs: 1454,
  salesBackedDiscs: 0,
  salesRun: null,
  salesBudgetLeft: 600,
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
    { movieId: HEAT, title: 'Heat', year: 1995, posterPath: null, formatCode: '4k_uhd', price: '34.99', currency: 'GBP', basis: 'current asking prices', sampleSize: 7, valueBasis: 'used', factor: null, low: '30.00', high: '40.00', valuedAs: 'as used copies', checkedAt: '2026-09-26T03:00:00Z', copies: 1 },
  ],
  bestReviewed: [{ movieId: ALIEN, title: 'Alien', year: 1979, posterPath: null, overall: 4.5, outOf: 5, formatCode: '4k_uhd', strength: 'picture', scores: [{ heading: 'Video 4K', score: 5 }] }],
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
    personProfilePath: null,
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

function renderHome(client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
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
  onlineManager.setOnline(true)
  vi.clearAllMocks()
})

describe('Home as rows, the collection first — Batch W2', () => {
  it('shows AA8’s private five-image MARKS banner above the Home rows', async () => {
    renderHome()
    const hero = await screen.findByTestId('private-hero')
    expect(hero.getAttribute('data-hero')).toBe('five')
    expect(hero.getAttribute('alt')).toContain('MARKS')
    expect(hero.compareDocumentPosition(screen.getByRole('heading', { level: 2, name: 'The collection' }))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })

  it('runs the collection first, then disc releases, the highlights, memories and completion', async () => {
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Completion' })
    await screen.findByRole('heading', { level: 2, name: 'Coming to disc' })
    expect(headings()).toEqual([
      'The collection',
      'Coming to disc',
      'Most rewatched',
      'Most valuable discs',
      'Best discs',
      'On this day',
      'Worth a rewatch',
      'Completion',
    ])
  })

  it('says what each count is: films owned, and copies split into discs and downloads — Batch X12a', async () => {
    renderHome()
    expect(await screen.findByText('Titles owned')).not.toBeNull()
    expect(screen.getByText('Copies catalogued')).not.toBeNull()
    expect(screen.getByText('1,880 physical · 422 download')).not.toBeNull()
    expect(screen.getByText('422 include both')).not.toBeNull()
    fireEvent.click(screen.getByText('Collection breakdown'))
    expect(screen.getByText('Formats (copies)')).not.toBeNull()
    expect(screen.getByText('Where they live (copies)')).not.toBeNull()
  })

  it('keeps other Home shelves sideways and makes the collection summary fixed — owner pick AA3', async () => {
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Completion' })
    for (const heading of screen.getAllByRole('heading', { level: 2 })) {
      const section = heading.closest('section')
      expect(section, heading.textContent ?? '').not.toBeNull()
      const rows = [...(section as HTMLElement).querySelectorAll('ul')].filter((list) =>
        list.className.split(/\s+/).includes('overflow-x-auto'),
      )
      if (heading.textContent === 'The collection') {
        expect(rows.length).toBe(0)
        expect(within(section as HTMLElement).getByRole('list', { name: 'The collection in numbers' }).className).toContain('grid-cols-2')
      } else {
        expect(rows.length, heading.textContent ?? '').toBeGreaterThan(0)
      }
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
    expect(numbers.getByText('1,454 of 1,880 physical copies priced')).not.toBeNull()
    expect(numbers.getByText('1,888')).not.toBeNull()
  })

  it('links the collection heading to the Archive — AA1', async () => {
    renderHome()
    const collection = await screen.findByRole('heading', { level: 2, name: 'The collection' })
    const section = collection.closest('section') as HTMLElement

    expect(within(section).getByRole('link', { name: 'Browse the archive' }).getAttribute('href')).toBe('/movies')
  })

  it('counts sales-backed discs beside the worth on Home', async () => {
    api.fetchCollectionValue.mockResolvedValue({ ...VALUE, salesBackedDiscs: 3 })
    renderHome()
    const numbers = within(await screen.findByRole('list', { name: 'The collection in numbers' }))
    expect(numbers.getByText('1,454 of 1,880 physical copies priced')).not.toBeNull()
    expect(numbers.getByText('3 based on observed sales')).not.toBeNull()
    fireEvent.click(numbers.getByText('How this estimate works'))
    expect(numbers.getByText(/At least three observed sales in 90 days use the median/)).not.toBeNull()
    expect(numbers.getByText(/a Best Offer may have closed below its advertised price/)).not.toBeNull()
  })

  it('tells a viewer explicitly when there is no stored estimate', async () => {
    auth.role = 'viewer'
    api.fetchCollectionValue.mockResolvedValue({ ...VALUE, total: null, pricedDiscs: 0 })
    renderHome()
    const numbers = within(await screen.findByRole('list', { name: 'The collection in numbers' }))
    await waitFor(() => expect(api.fetchCollectionValue).toHaveBeenCalled())
    expect(numbers.getByText('Estimated used value')).not.toBeNull()
    expect(numbers.getByText('Not valued yet')).not.toBeNull()
    expect(numbers.queryByRole('link', { name: 'Value it in Admin' })).toBeNull()
  })

  it('keeps actual physical counts and overlap when valuation fails', async () => {
    api.fetchStats.mockResolvedValue({ ...STATS, totalItems: 1927, downloadCopies: 589, physicalCopies: 1472, physicalAndDownloadCopies: 134 })
    api.fetchCollectionValue.mockRejectedValue(new Error('Value service unavailable'))
    renderHome()
    const numbers = within(await screen.findByRole('list', { name: 'The collection in numbers' }))
    expect(numbers.getByText('1,472 physical · 589 download')).not.toBeNull()
    expect(numbers.getByText('134 include both')).not.toBeNull()
    expect(numbers.queryByText(/1,338/)).toBeNull()
    await waitFor(() => expect(numbers.getByText('Unavailable')).not.toBeNull())
  })

  it('keeps the Archive available while stats load and when they fail', async () => {
    api.fetchStats.mockRejectedValue(new Error('Stats unavailable'))
    renderHome()
    expect(screen.getByRole('link', { name: 'Browse the archive' })).not.toBeNull()
    expect(await screen.findByText('The collection ledger is unavailable')).not.toBeNull()
    expect(screen.getByRole('link', { name: 'Browse the archive' })).not.toBeNull()
  })

  it('shows cached counts and an explicit offline value state when value was never cached', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['stats'], STATS)
    onlineManager.setOnline(false)
    renderHome(client)
    expect(await screen.findByText('Reconnect to load the stored estimate. Collection counts are still available.')).not.toBeNull()
    expect(screen.getByText('1,880 physical · 422 download')).not.toBeNull()
    expect(screen.queryByText('Loading the stored estimate')).toBeNull()
  })

  it('keeps a cached value with an explicit failed-refresh warning', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['collection-value'], VALUE)
    api.fetchCollectionValue.mockRejectedValue(new Error('Refresh failed'))
    renderHome(client)
    expect(await screen.findByText('The latest value could not be loaded; showing the stored estimate.')).not.toBeNull()
    expect(screen.getByText('≈ £1,903')).not.toBeNull()
  })

  it('does not invent a physical count when an older API omits the new fields', async () => {
    const oldStats = { ...STATS }
    delete oldStats.physicalCopies
    delete oldStats.physicalAndDownloadCopies
    api.fetchStats.mockResolvedValue(oldStats)
    renderHome()
    expect(await screen.findByText('Physical/download split is temporarily unavailable.')).not.toBeNull()
    expect(screen.queryByText(/1,458 physical/)).toBeNull()
    expect(screen.getByText('Copies catalogued')).not.toBeNull()
  })

  it.each(['admin', 'viewer'] as const)('retains diary and TMDB counts with their true meaning for %s', async (role) => {
    auth.role = role
    renderHome()
    const numbers = within(await screen.findByRole('list', { name: 'The collection in numbers' }))
    expect(numbers.getByText("You've watched")).not.toBeNull()
    expect(numbers.getByText('594')).not.toBeNull()
    expect(numbers.getByText("Distinct titles in your diary, including titles you don't own")).not.toBeNull()
    expect(numbers.getByText('Matched on TMDB')).not.toBeNull()
    expect(numbers.getByText('1,678')).not.toBeNull()
    expect(numbers.getByText('Of 1,888 owned titles. A match can still need checking.')).not.toBeNull()
  })

  it('makes dated purchase values available without hover and explains limited coverage', async () => {
    api.fetchStats.mockResolvedValue({ ...STATS, itemsWithPrice: 2, spendOverTime: [{ month: '2026-09', spentCents: 1299, cumulativeCents: 1299, itemCount: 1 }] })
    renderHome()
    await screen.findByRole('list', { name: 'The collection in numbers' })
    fireEvent.click(screen.getByText('Collection breakdown'))
    expect(screen.getByText('Recorded spending')).not.toBeNull()
    expect(screen.getByText(/not the collection's lifetime cost/)).not.toBeNull()
    fireEvent.click(screen.getByText('Monthly spending figures'))
    expect(screen.getByText('£12.99 · £12.99 total')).not.toBeNull()
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
