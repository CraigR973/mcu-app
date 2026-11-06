// @vitest-environment happy-dom
import { onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CompletionSet, Stats } from '@mcu/shared'

import type { CalendarEntry, CollectionValue, Highlights } from '@/lib/api'
import { CINEMA_NOW, filmsFixture } from './cinema-films-fixture'

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
  // AC1: Home's "Needs you" row, for everyone. Nothing to do here unless a test says so.
  fetchNeedsYou: vi.fn().mockResolvedValue({ items: [] }),
  // AC4: the cinema strip's read. Refused unless a test says otherwise, so Home keeps its card.
  fetchCinemaFilms: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))
vi.mock('@/components/brand/HomeBanner', () => ({
  HomeBanner: () => <div data-testid="home-banner" role="img" aria-label="MARK'S Cinematic Universe" />,
}))

import DashboardPage from './DashboardPage'

const HEAT = '3f2504e0-4f89-41d3-9a0c-0305e82c3401'
const ALIEN = '3f2504e0-4f89-41d3-9a0c-0305e82c3402'
// AC2: a film per module, so each shows; the no-repeat test overlaps them on purpose.
const BLOOD = '3f2504e0-4f89-41d3-9a0c-0305e82c3403'
const JAWS = '3f2504e0-4f89-41d3-9a0c-0305e82c3404'
const CHINATOWN = '3f2504e0-4f89-41d3-9a0c-0305e82c3405'
const ZODIAC = '3f2504e0-4f89-41d3-9a0c-0305e82c3406'
const THIEF = '3f2504e0-4f89-41d3-9a0c-0305e82c3407'

const STATS: Stats = {
  totalMovies: 1888,
  totalItems: 1880,
  downloadCopies: 422,
  physicalCopies: 1880,
  physicalAndDownloadCopies: 422,
  identifiedMovies: 1678,
  watchedMovies: 594,
  ownedWatchedMovies: 482,
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
  movieId: BLOOD,
  tmdbId: null,
}

const HIGHLIGHTS: Highlights = {
  topRated: { items: [{ movieId: HEAT, title: 'Heat', year: 1995, posterPath: null, ratings: [{ personName: 'Craig', rating: 5 }] }], ratedBy: ['Craig'], notRatedBy: ['Mark'] },
  mostRewatched: [{ movieId: JAWS, title: 'Jaws', year: 1975, posterPath: null, viewings: 3, byPerson: [{ personName: 'Craig', viewings: 3 }] }],
  mostValuable: [
    { movieId: HEAT, title: 'Heat', year: 1995, posterPath: null, formatCode: '4k_uhd', price: '34.99', currency: 'GBP', basis: 'current asking prices', sampleSize: 7, valueBasis: 'used', factor: null, low: '30.00', high: '40.00', valuedAs: 'as used copies', checkedAt: '2026-09-26T03:00:00Z', copies: 1 },
  ],
  bestReviewed: [{ movieId: CHINATOWN, title: 'Chinatown', year: 1974, posterPath: null, overall: 4.5, outOf: 5, formatCode: '4k_uhd', strength: 'picture', scores: [{ heading: 'Video 4K', score: 5 }] }],
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
  api.fetchNeedsYou.mockResolvedValue({ items: [] })
  api.fetchStats.mockResolvedValue(STATS)
  api.fetchCollectionValue.mockResolvedValue(VALUE)
  api.fetchCalendar.mockResolvedValue({ items: [RELEASE], total: 1, refreshedAt: null })
  api.fetchHighlights.mockResolvedValue(HIGHLIGHTS)
  api.fetchOnThisDayMemories.mockResolvedValue([
    { id: '3f2504e0-4f89-41d3-9a0c-0305e82c3701', movieId: ZODIAC, movieTitle: 'Zodiac', posterPath: null, watchedAt: '2024-10-05', yearsAgo: 2, personalRating: null },
  ])
  api.fetchRewatchSuggestions.mockResolvedValue([
    { movieId: ALIEN, movieTitle: 'Alien', posterPath: null, lastWatchedAt: '2025-01-12', personalRating: 4.5 },
    { movieId: THIEF, movieTitle: 'Thief', posterPath: null, lastWatchedAt: '2024-03-19', personalRating: 5 },
  ])
  api.fetchCompletionInsights.mockResolvedValue({ items: SETS, total: SETS.length, oldestRefresh: null })
  api.fetchSmartCollections.mockResolvedValue({ items: [], total: 0 })
  api.fetchActivity.mockResolvedValue({ items: [] })
  api.fetchCinemaFilms.mockRejectedValue(new Error('No cinema read in this test'))
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

describe('Home as one ledger and varied modules — AC2, Craig\'s pick A (#337)', () => {
  it('shows banner T1 above Home\'s modules', async () => {
    renderHome()
    const banner = await screen.findByTestId('home-banner')
    expect(banner.getAttribute('aria-label')).toBe("MARK'S Cinematic Universe")
    expect(banner.compareDocumentPosition(screen.getByRole('heading', { level: 2, name: 'The collection' }))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })

  it('runs the ledger, the featured film, three rows, the closest sets and the cinemas', async () => {
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Closest to complete' })
    await screen.findByRole('heading', { level: 2, name: 'Coming to disc' })
    expect(headings()).toEqual([
      'The collection',
      'Alien',
      'Coming to disc',
      'Highlights',
      'For you',
      'Closest to complete',
    ])
    expect(screen.getByRole('link', { name: 'At the cinema' })).not.toBeNull()
  })

  it('features a film Home already read, with Feeling lucky inside it', async () => {
    renderHome()
    const title = await screen.findByRole('heading', { level: 2, name: 'Alien' })
    const card = within(title.closest('section') as HTMLElement)
    expect(card.getByText('Worth a rewatch')).not.toBeNull()
    expect(card.getByText('You gave it ★ 4½ and last saw it on 12 Jan 2025.')).not.toBeNull()
    expect(card.getByRole('link', { name: 'Open the film' }).getAttribute('href')).toBe(`/movies/${ALIEN}`)
    const lucky = within(card.getByRole('group', { name: 'Feeling lucky' }))
    expect(lucky.getByRole('button', { name: 'Deal another' })).not.toBeNull()
    expect(lucky.getByRole('checkbox', { name: 'Only films I haven’t watched' })).not.toBeNull()
  })

  it('shows no film twice in one load', async () => {
    // The 4 Nov overlap: one favourite in the rewatch list, Most rewatched, Best discs and On this day.
    api.fetchRewatchSuggestions.mockResolvedValue([
      { movieId: ALIEN, movieTitle: 'Alien', posterPath: null, lastWatchedAt: '2025-01-12', personalRating: 4.5 },
      { movieId: JAWS, movieTitle: 'Jaws', posterPath: null, lastWatchedAt: '2024-03-19', personalRating: 5 },
    ])
    api.fetchHighlights.mockResolvedValue({
      ...HIGHLIGHTS,
      mostRewatched: [{ ...HIGHLIGHTS.mostRewatched[0], movieId: ALIEN, title: 'Alien' }, HIGHLIGHTS.mostRewatched[0]],
      bestReviewed: [{ ...HIGHLIGHTS.bestReviewed[0], movieId: ALIEN, title: 'Alien' }],
    })
    api.fetchOnThisDayMemories.mockResolvedValue([
      { id: '3f2504e0-4f89-41d3-9a0c-0305e82c3702', movieId: JAWS, movieTitle: 'Jaws', posterPath: null, watchedAt: '2024-10-05', yearsAgo: 2, personalRating: null },
    ])
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Highlights' })
    const filmLinks = screen.getAllByRole('link').map((link) => link.getAttribute('href')).filter((href) => href?.startsWith('/movies/'))
    expect(filmLinks.filter((href) => href === `/movies/${ALIEN}`)).toHaveLength(1)
    expect(filmLinks.filter((href) => href === `/movies/${JAWS}`)).toHaveLength(1)
    // Best discs had only Alien, already featured, so its tab is not offered.
    expect(screen.queryByRole('tab', { name: 'Best discs' })).toBeNull()
  })

  it('says what each count is, once: titles, then copies on disc and digital in one line', async () => {
    renderHome()
    const numbers = within(await screen.findByRole('list', { name: 'The collection in numbers' }))
    expect(numbers.getByText('titles')).not.toBeNull()
    expect(numbers.getByText('1,888')).not.toBeNull()
    expect(numbers.getByText(/copies · 1,880 on disc · 422 digital · 422 both/)).not.toBeNull()
    fireEvent.click(screen.getByText('Collection breakdown'))
    expect(screen.getByText('Where they live (copies)')).not.toBeNull()
    // The formats are the ledger's stacked bar; the breakdown does not draw them again.
    expect(screen.queryByText('Formats (copies)')).toBeNull()
  })

  it('keeps at most four sideways rows; the ledger, the featured film and the sets are fixed', async () => {
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Closest to complete' })
    await screen.findByRole('heading', { level: 2, name: 'For you' })
    const sideways = [...document.querySelectorAll('ul')].filter((list) => list.className.split(/\s+/).includes('overflow-x-auto'))
    expect(sideways.length).toBeLessThanOrEqual(4)
    for (const name of ['The collection', 'Alien', 'Closest to complete']) {
      const section = screen.getByRole('heading', { level: 2, name }).closest('section') as HTMLElement
      expect([...section.querySelectorAll('ul')].some((list) => list.className.includes('overflow-x-auto')), name).toBe(false)
    }
  })

  it('has no Add a disc, no Most watched, no Top rated and no valuation or bid-trial controls, even for an admin', async () => {
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Closest to complete' })
    expect(screen.queryByRole('link', { name: /Add a disc/ })).toBeNull()
    expect(screen.queryByText('Most watched')).toBeNull()
    expect(screen.queryByRole('tab', { name: 'Top rated' })).toBeNull()
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

  it('counts sales-backed discs beside the worth, its method behind a tap', async () => {
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
    expect(numbers.getByText(/copies · 1,472 on disc · 589 digital · 134 both/)).not.toBeNull()
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
    client.setQueryData(['stats', 'p'], STATS)
    onlineManager.setOnline(false)
    renderHome(client)
    expect(await screen.findByText('Reconnect to load the stored estimate. Collection counts are still available.')).not.toBeNull()
    expect(screen.getByText(/copies · 1,880 on disc · 422 digital/)).not.toBeNull()
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
    expect(await screen.findByText(/Physical\/download split is temporarily unavailable\./)).not.toBeNull()
    expect(screen.queryByText(/1,458 on disc/)).toBeNull()
    expect(screen.getByText(/copies owned/)).not.toBeNull()
  })

  it.each(['admin', 'viewer'] as const)('shows owned-watch coverage as a share of the titles owned, and no TMDB match count, for %s', async (role) => {
    auth.role = role
    renderHome()
    const numbers = within(await screen.findByRole('list', { name: 'The collection in numbers' }))
    expect(numbers.getByText("You've watched")).not.toBeNull()
    expect(numbers.getByText('26%')).not.toBeNull()
    expect(numbers.getByText('482 of 1,888 titles you own')).not.toBeNull()
    expect(numbers.getByRole('progressbar', { name: 'Share of the collection you have watched' }).getAttribute('aria-valuenow')).toBe('26')
    // AC2: "Matched on TMDB" left Home; Identify films and its attention checks keep it.
    expect(screen.queryByText('Matched on TMDB')).toBeNull()
  })

  it('does not replace absent owned-watch coverage with the diary count or an invented zero', async () => {
    const oldStats = { ...STATS }
    delete oldStats.ownedWatchedMovies
    api.fetchStats.mockResolvedValue(oldStats)
    renderHome()
    const numbers = within(await screen.findByRole('list', { name: 'The collection in numbers' }))
    expect(numbers.getByText('Unavailable')).not.toBeNull()
    expect(numbers.getByText('Watched coverage is unavailable in this saved response.')).not.toBeNull()
    expect(numbers.queryByText(/594/)).toBeNull()
    expect(numbers.queryByText(/^0 of 1,888/)).toBeNull()
  })

  it('shows genuine zero and an empty collection without percentage arithmetic', async () => {
    api.fetchStats.mockResolvedValue({ ...STATS, totalMovies: 0, ownedWatchedMovies: 0 })
    renderHome()
    expect(await screen.findByText('0 of 0 titles you own')).not.toBeNull()
    expect(screen.queryByText('Watched coverage is unavailable in this saved response.')).toBeNull()
    expect(screen.queryByRole('progressbar', { name: 'Share of the collection you have watched' })).toBeNull()
  })

  it('shows the formats as one stacked bar before the full breakdown is opened', async () => {
    renderHome()
    const preview = await screen.findByRole('region', { name: 'Formats at a glance' })
    expect(within(preview).getByText('Blu-ray')).not.toBeNull()
    expect(within(preview).getByText('900')).not.toBeNull()
    expect(within(preview).getByText('Copies can carry more than one format; these counts overlap.')).not.toBeNull()
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
    api.fetchRewatchSuggestions.mockResolvedValue([{ movieId: ALIEN, movieTitle: 'Alien', posterPath: null, lastWatchedAt: '2025-01-12', personalRating: 4.5 }])
    api.fetchCalendar.mockResolvedValue({ items: [], total: 0, refreshedAt: null })
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'Closest to complete' })
    await screen.findByRole('heading', { level: 2, name: 'Highlights' })
    // Alien is featured, so For you has nothing left in it.
    expect(headings()).not.toContain('For you')
    expect(headings()).not.toContain('Coming to disc')
  })

  it('puts the sets closest to complete first, as a short list, and links to all of them', async () => {
    renderHome()
    const heading = await screen.findByRole('heading', { level: 2, name: 'Closest to complete' })
    const section = within(heading.closest('section') as HTMLElement)
    const names = section.getAllByRole('button').map((button) => button.querySelector('span span')?.textContent)
    expect(names).toEqual(['Michael Mann', 'John Carpenter', 'Bess Flowers'])
    expect(section.getByRole('link', { name: 'All 3' }).getAttribute('href')).toBe('/insights')
  })

  it('opens the set tapped, not the list — the bug W2 found', async () => {
    api.fetchCompletionSet.mockResolvedValue({ ...SETS[1], films: [] })
    renderHome()
    const heading = await screen.findByRole('heading', { level: 2, name: 'Closest to complete' })
    fireEvent.click(within(heading.closest('section') as HTMLElement).getByText('Michael Mann'))

    await waitFor(() => expect(api.fetchCompletionSet).toHaveBeenCalledWith(SETS[1].id))
    expect(screen.queryByRole('heading', { level: 2, name: 'The collection' })).toBeNull()

    // Its back control names where it goes, and goes there.
    fireEvent.click(screen.getByRole('button', { name: 'Home' }))
    expect(await screen.findByRole('heading', { level: 2, name: 'The collection' })).not.toBeNull()
  })

  it('makes no more requests than before AC2: one read per module, the featured film reusing them', async () => {
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'For you' })
    for (const read of [api.fetchStats, api.fetchCollectionValue, api.fetchCalendar, api.fetchHighlights, api.fetchOnThisDayMemories, api.fetchRewatchSuggestions, api.fetchNeedsYou, api.fetchAttention]) {
      expect(read).toHaveBeenCalledTimes(1)
    }
  })
})

describe('Needs you, at the top for everyone — AC1 (#335)', () => {
  const PUT_BACK = {
    kind: 'putBack' as const,
    loanId: '3f2504e0-4f89-41d3-9a0c-0305e82c3801',
    movieId: HEAT,
    movieTitle: 'Heat',
    posterPath: null,
    locationLabel: 'Front 2nd',
    borrowerName: 'Craig',
    borrowerIsYou: false,
    lentDate: '2026-10-21',
    returnedDate: '2026-10-28',
    neededBy: null,
    dueDate: null,
    daysOverdue: null,
    daysOut: null,
  }

  it('shows a viewer what is theirs to do, above the collection, with no admin row', async () => {
    auth.role = 'viewer'
    api.fetchNeedsYou.mockResolvedValue({ items: [PUT_BACK] })
    renderHome()
    const row = await screen.findByRole('region', { name: 'Needs you' })
    const link = within(row).getByRole('link', { name: /Put back Heat/ })
    expect(link.getAttribute('href')).toBe(`/loans?view=back&loan=${PUT_BACK.loanId}`)
    expect(row.compareDocumentPosition(screen.getByRole('heading', { level: 2, name: 'The collection' }))).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
    expect(api.fetchAttention).not.toHaveBeenCalled()
  })

  it('sits above Craig’s own Needs attention, which is unchanged', async () => {
    api.fetchNeedsYou.mockResolvedValue({ items: [PUT_BACK] })
    api.fetchAttention.mockResolvedValue({
      checkedAt: '2026-11-04T08:00:00Z',
      items: [{ key: 'check:stale', message: 'The daily check has not run.', since: null, noteId: null }],
    })
    renderHome()
    const needsYou = await screen.findByRole('region', { name: 'Needs you' })
    const attention = await screen.findByRole('heading', { level: 2, name: 'Needs attention' })
    expect(needsYou.compareDocumentPosition(attention)).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('holds Feeling lucky until Needs you has arrived, so a tap cannot land on a moving row', async () => {
    let arrive!: (value: { items: typeof PUT_BACK[] }) => void
    api.fetchNeedsYou.mockReturnValue(new Promise((resolve) => { arrive = resolve }))
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'The collection' })
    expect(screen.getByRole('link', { name: 'At the cinema' }).getAttribute('aria-disabled')).toBe('true')
    arrive({ items: [PUT_BACK] })
    await screen.findByRole('region', { name: 'Needs you' })
    await waitFor(() => expect(screen.getByRole('link', { name: 'At the cinema' }).getAttribute('aria-disabled')).toBeNull())
  })
})

describe('At the cinema on Home — AC4', () => {
  it('becomes a poster strip of this week’s films, last on Home, opening each film’s page', async () => {
    vi.spyOn(Date, 'now').mockReturnValue(CINEMA_NOW)
    api.fetchCinemaFilms.mockResolvedValue(filmsFixture())
    renderHome()
    const strip = await screen.findByRole('region', { name: 'At the cinema' })
    expect(within(strip).getByRole('link', { name: 'At the cinema' }).getAttribute('href')).toBe('/movie-night/cinema')
    const cards = within(within(strip).getByRole('list', { name: 'This week at the cinema' })).getAllByRole('listitem')
    expect(cards.map((card) => card.textContent)).toEqual(['A returning favouriteRerun2 cinemas', 'A current first runFirst runODEON Kilmarnock'])
    expect(within(cards[0]).getByRole('link').getAttribute('href')).toBe('/movie-night/cinema/tmdb-1417')
    expect(headings().at(-1)).toBe('At the cinema')
    vi.restoreAllMocks()
  })

  it('keeps its card while the cinemas have no film with a poster, and guards every way in', async () => {
    const bare = filmsFixture()
    for (const film of bare.films) film.posterPath = null
    api.fetchCinemaFilms.mockResolvedValue(bare)
    let arrive!: (value: { items: [] }) => void
    api.fetchNeedsYou.mockReturnValue(new Promise((resolve) => { arrive = resolve }))
    renderHome()
    await screen.findByRole('heading', { level: 2, name: 'The collection' })
    expect(screen.getByRole('link', { name: 'At the cinema' }).getAttribute('aria-disabled')).toBe('true')
    arrive({ items: [] })
    await waitFor(() => expect(screen.getByRole('link', { name: 'At the cinema' }).getAttribute('aria-disabled')).toBeNull())
    expect(screen.queryByRole('list', { name: 'This week at the cinema' })).toBeNull()
  })
})
