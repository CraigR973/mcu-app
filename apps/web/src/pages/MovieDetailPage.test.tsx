// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MovieDetailPage from './MovieDetailPage'
import { fetchCopies, fetchMovie, type CollectionCopy, type MovieDetail } from '@/lib/api'

vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { role: 'viewer' } }),
}))

vi.mock('@/hooks/useRecentItems', () => ({
  useRecentItems: () => ({ addRecentItem: vi.fn() }),
}))

vi.mock('@/components/movies/WatchPanel', () => ({
  default: () => <div>Watch log</div>,
}))

vi.mock('@/components/collection/PhotoGallery', () => ({
  PhotoGallery: () => <div>Disc photos loaded</div>,
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    fetchMovie: vi.fn(),
    fetchCopies: vi.fn(),
  }
})

const MOVIE_ID = '3f2504e0-4f89-11d3-9a0c-0305e82c3301'
const COPY_ID = '3f2504e0-4f89-11d3-9a0c-0305e82c3302'

const MOVIE: MovieDetail = {
  id: MOVIE_ID,
  title: 'The Red Shoes',
  originalTitle: 'The Red Shoes',
  year: 1948,
  posterPath: null,
  backdropPath: null,
  tmdbRating: 8.1,
  runtimeMinutes: 133,
  bestFormatOwned: '4k_uhd',
  bestHdrOwned: null,
  bestAudioOwned: null,
  identified: true,
  copyCount: 1,
  locations: [{ section: 'Front', shelf: '2nd', label: 'Front 2nd' }],
  watched: false,
  lastWatchedAt: null,
  editions: ['Criterion Collection'],
  imdbId: 'tt0040725',
  overview: 'A ballerina must choose between love and art.',
  tagline: null,
  genres: [],
  cast: [],
  crew: [],
  trailerKey: null,
  letterboxdSlug: 'the-red-shoes',
  mediaType: 'film',
}

const COPY: CollectionCopy = {
  id: COPY_ID,
  formats: ['4k_uhd'],
  location: 'Front 2nd shelf',
  section: 'Front',
  shelf: '2nd',
  // Batch U2: the spreadsheet's grouping, and the copy's own edition beside it. The grouping
  // held "Criterion Collection" here while it was labelled "Collector edition".
  subCategory: 'Powell & Pressburger',
  edition: 'Criterion Collection',
  notes: null,
  purchasePrice: '24.99',
  purchaseSource: 'BFI Shop',
  purchaseDate: '2026-09-01',
  condition: 'like_new',
  hasPlaybackIssues: false,
  playbackNotes: null,
  videoSpecs: null,
  audioSpecs: null,
  specialFeatures: null,
  regionCode: 'Free',
  releaseLabel: 'The Criterion Collection',
  listingStatus: 'in_collection',
  ebayListingUrl: null,
  listingPrice: null,
  updatedAt: '2026-09-08T14:00:00Z',
  valuation: {
    formatCode: '4k_uhd',
    status: 'priced',
    price: '22.50',
    currency: 'GBP',
    sampleSize: 14,
    conditionLabel: 'New',
    checkedAt: '2026-09-24T03:05:00Z',
    basis: 'current asking prices',
    minSample: 3,
    soldListingsUrl: null,
  },
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, networkMode: 'always' },
      mutations: { retry: false, networkMode: 'always' },
    },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/movies/${MOVIE_ID}`]}>
        <Routes>
          <Route path="/movies/:id" element={<MovieDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.mocked(fetchMovie).mockResolvedValue(MOVIE)
  vi.mocked(fetchCopies).mockResolvedValue([COPY])
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('MovieDetailPage collection answer', () => {
  it('opens on owned copies and surfaces the edition, sub-category, label and shelf', async () => {
    renderPage()

    expect(await screen.findByText('Criterion Collection')).not.toBeNull()
    expect(screen.getByText('Edition')).not.toBeNull()
    // Batch U2: the grouping is called what the spreadsheet calls it, not "Collector edition".
    expect(screen.getByText('Sub-category')).not.toBeNull()
    expect(screen.getByText('Powell & Pressburger')).not.toBeNull()
    expect(screen.queryByText('Collector edition')).toBeNull()
    expect(screen.getByText('Release label')).not.toBeNull()
    expect(screen.getByText('The Criterion Collection')).not.toBeNull()
    expect(screen.getByText('Front 2nd shelf')).not.toBeNull()
    expect(screen.getByRole('tab', { name: /Owned copies/ }).getAttribute('aria-selected')).toBe('true')
  })

  it("shows a viewer the disc's stored value, with what it rests on", async () => {
    renderPage()

    expect(await screen.findByText('£22.50')).not.toBeNull()
    expect(screen.getByText(/Last valued · current asking prices/)).not.toBeNull()
    expect(screen.getByText(/median of 14 listings · New · checked 24 Sep 2026/)).not.toBeNull()
    // The live check spends an eBay lookup, so it stays with the admin.
    expect(screen.queryByRole('button', { name: /What is it worth/ })).toBeNull()
  })

  it('says a disc was not priced, and why, rather than showing a guess', async () => {
    vi.mocked(fetchCopies).mockResolvedValue([
      { ...COPY, valuation: { ...COPY.valuation!, status: 'not_priced', price: null, sampleSize: 2 } },
    ])
    renderPage()

    expect(
      await screen.findByText(/Not priced when checked on 24 Sep 2026: eBay had only 2 matching listings, and a price needs at least 3/),
    ).not.toBeNull()
  })

  it('reports a copy request failure instead of claiming there are no copies', async () => {
    vi.mocked(fetchCopies).mockRejectedValueOnce(new Error('Copies API unavailable'))
    renderPage()

    expect(await screen.findByText('Could not load the owned copies')).not.toBeNull()
    expect(screen.getByText('Copies API unavailable')).not.toBeNull()
    expect(screen.queryByText('No live copies in the collection')).toBeNull()
  })
})

describe('MovieDetailPage tabs', () => {
  // Batch U3's browser check, at 375 px on a touch screen: `touch-target`'s 44px minimum
  // width replaced the flex item's automatic one, so the tabs shrank below their labels and
  // the copy count spilled onto "Overview". No layout here to measure; this pins the fix.
  it('never shrinks a tab below its label, so the strip scrolls instead', async () => {
    renderPage()
    await screen.findByText('Criterion Collection')

    const tabs = screen.getAllByRole('tab')
    expect(tabs.length).toBeGreaterThan(1)
    for (const tab of tabs) {
      expect(tab.className).toMatch(/(^|\s)shrink-0(\s|$)/)
      expect(tab.className).toContain('whitespace-nowrap')
    }
    expect(screen.getByRole('tablist', { name: 'Film details' }).className).toContain('overflow-x-auto')
  })
})

function Where() {
  return <output aria-label="Current page">{useLocation().pathname}</output>
}

/** The film page with `entries` as its history, the film last. */
function renderPageFrom(entries: string[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, networkMode: 'always' } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={entries} initialIndex={entries.length - 1}>
        <Routes>
          <Route path="/movies/:id" element={<MovieDetailPage />} />
          <Route path="*" element={<p>Somewhere else</p>} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('MovieDetailPage back button — Batch V1, snag 5', () => {
  it('returns to where the film was opened from, not always to the Archive', async () => {
    // Snag 5: a film opened from Deals went "Back to collection", wherever it came from.
    renderPageFrom(['/deals', `/movies/${MOVIE_ID}`])
    fireEvent.click(await screen.findByRole('button', { name: 'Back' }))
    await waitFor(() => expect(screen.getByLabelText('Current page').textContent).toBe('/deals'))
  })

  it('goes to the Archive when there is no history behind the film', async () => {
    // Opened from a notification or a link: going back would leave the app.
    renderPageFrom([`/movies/${MOVIE_ID}`])
    fireEvent.click(await screen.findByRole('button', { name: 'Back' }))
    await waitFor(() => expect(screen.getByLabelText('Current page').textContent).toBe('/movies'))
  })

  it('is hidden below 1024px, where the top bar carries the arrow', async () => {
    // No layout engine here to measure; the classes are the whole of the rule.
    renderPageFrom([`/movies/${MOVIE_ID}`])
    const back = await screen.findByRole('button', { name: 'Back' })
    expect(back.className).toMatch(/(^|\s)hidden(\s|$)/)
    expect(back.className).toContain('lg:inline-flex')
    expect(screen.queryByRole('link', { name: /Back to collection/ })).toBeNull()
  })
})
