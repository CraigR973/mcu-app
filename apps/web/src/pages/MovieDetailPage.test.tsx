// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MovieDetailPage from './MovieDetailPage'
import { fetchCandidates, fetchCopies, fetchMovie, identifyMovie, type CollectionCopy, type MovieDetail } from '@/lib/api'
import { deleteOrQueue, updateOrQueue } from '@/lib/sync'

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
    fetchCandidates: vi.fn(),
    identifyMovie: vi.fn(),
    fetchFacets: vi.fn().mockResolvedValue({ sections: [], allSections: [] }),
  }
})

vi.mock('@/lib/sync', () => ({
  deleteOrQueue: vi.fn().mockResolvedValue({ queued: false }),
  updateOrQueue: vi.fn().mockResolvedValue({ queued: false }),
}))

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
  setAsideAs: null,
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
  reviews: [],
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
    valueBasis: 'new_scaled',
    factor: '0.62',
    low: '28.00',
    high: '45.00',
    usedCount: 2,
    newCount: 14,
    valuedAs: 'as used copies',
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
    expect(screen.getByText(/Last valued as a used copy · current asking prices/)).not.toBeNull()
    expect(
      screen.getByText(
        /too few used listings: New's median × 0.62, from 14 new listings, £28.00–£45.00 · checked 24 Sep 2026/,
      ),
    ).not.toBeNull()
    // The live check spends an eBay lookup, so it stays with the admin.
    expect(screen.queryByRole('button', { name: /What is it worth/ })).toBeNull()
  })

  it('says a disc was not priced, and why, rather than showing a guess', async () => {
    vi.mocked(fetchCopies).mockResolvedValue([
      {
        ...COPY,
        valuation: {
          ...COPY.valuation!,
          status: 'not_priced',
          price: null,
          sampleSize: 2,
          valueBasis: null,
          factor: null,
          low: null,
          high: null,
          usedCount: 2,
          newCount: 1,
        },
      },
    ])
    renderPage()

    expect(
      await screen.findByText(
        /Not priced when checked on 24 Sep 2026: eBay had 2 used listings and 1 new listing, and a value needs at least 3 of one kind/,
      ),
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

// Batch Y1, `DECISIONS.md` #264: the mocked profile is Mark's (`viewer`). He adds discs
// since #155, and now edits, moves and deletes them; the eBay tools, photo uploads and the
// audit history stay Craig's.
describe('MovieDetailPage copy editing for Mark', () => {
  it('offers Mark the copy tools and keeps Craig-only tools hidden', async () => {
    renderPage()

    expect(await screen.findByRole('button', { name: /Edit copy/ })).not.toBeNull()
    expect(screen.getByRole('button', { name: /Mark damaged/ })).not.toBeNull()
    expect(screen.getByRole('link', { name: /Add a copy/ }).getAttribute('href')).toBe('/collection/add')
    expect(screen.queryByText('Value and resale')).toBeNull()
  })

  it('saves Mark\'s edit through the same queue-aware path as Craig\'s', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Edit copy/ }))
    fireEvent.click(screen.getByRole('button', { name: /Save changes/ }))

    await waitFor(() => expect(updateOrQueue).toHaveBeenCalledTimes(1))
    expect(vi.mocked(updateOrQueue).mock.calls[0]?.[2]).toMatchObject({
      section: 'Front',
      shelf: '2nd',
      baseUpdatedAt: COPY.updatedAt,
    })
  })

  it('asks before moving a copy to the Trash, and says only Craig can bring it back', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /Edit copy/ }))

    fireEvent.click(screen.getByRole('button', { name: 'Move to trash' }))
    expect(deleteOrQueue).not.toHaveBeenCalled()
    expect(screen.getByText(/Only Craig can bring it back/)).not.toBeNull()
    // While it asks, Save is gone: Mark tapped Save where "Yes" had been pushed off his
    // screen, and the disc stayed (13 Oct).
    expect(screen.queryByRole('button', { name: /Save changes/ })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Keep it' }))
    expect(screen.getByRole('button', { name: /Save changes/ })).not.toBeNull()
    expect(deleteOrQueue).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Move to trash' }))

    fireEvent.click(screen.getByRole('button', { name: /Yes, move to trash/ }))
    await waitFor(() => expect(deleteOrQueue).toHaveBeenCalledWith(COPY_ID, MOVIE_ID))
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

describe('MovieDetailPage reviews (Batch V9)', () => {
  it('shows the film\'s reviews above the tabs, whichever tab is open', async () => {
    vi.mocked(fetchMovie).mockResolvedValue({
      ...MOVIE,
      reviews: [
        {
          site: 'bluray_com',
          siteName: 'Blu-ray.com',
          url: 'https://www.blu-ray.com/movies/The-Red-Shoes-4K-Blu-ray/300000/',
          formatCode: '4k_uhd',
          title: 'The Red Shoes 4K Blu-ray',
          description: null,
          scores: [
            { heading: 'Movie', score: 5 },
            { heading: 'Overall', score: 4.5 },
          ],
          overall: 4.5,
          outOf: 5,
          scoresReadAt: '2026-10-03T02:20:00Z',
          note: null,
        },
      ],
    })
    renderPage()

    const link = await screen.findByRole('link', { name: 'Blu-ray.com (4K UHD)' })
    expect(link.getAttribute('href')).toBe('https://www.blu-ray.com/movies/The-Red-Shoes-4K-Blu-ray/300000/')
    expect(screen.getByText('4.5/5')).not.toBeNull()
    expect(screen.getByText('Movie 5.0')).not.toBeNull()
    // Copies is the tab open on arrival, and the reviews are still on the page.
    expect(screen.getByRole('tab', { selected: true }).textContent).toMatch(/Copies|Owned/)
  })

  it('shows no reviews line when none was found', async () => {
    renderPage()

    expect(await screen.findByText('Criterion Collection')).not.toBeNull()
    expect(screen.queryByText('Reviews:')).toBeNull()
  })
})


describe('MovieDetailPage set aside and series (Mark, 15 Oct; Batch Y3)', () => {
  it('offers TMDB series first for a series set aside, and identifies it as one', async () => {
    vi.mocked(fetchMovie).mockResolvedValue({
      ...MOVIE,
      title: 'Broadchurch',
      identified: false,
      setAsideAs: 'tv',
      mediaType: 'tv',
      overview: null,
    })
    vi.mocked(fetchCandidates).mockResolvedValue({
      movieId: MOVIE_ID,
      title: 'Broadchurch',
      query: 'Broadchurch',
      candidates: [{ tmdbId: 990, mediaType: 'film', title: 'Broadchurch', year: 1990, overview: '', posterPath: null, confidence: 0.6, titleSimilarity: 1 }],
      seriesCandidates: [{ tmdbId: 990, mediaType: 'tv', title: 'Broadchurch', year: 2013, overview: 'A boy is found dead.', posterPath: null, confidence: 1, titleSimilarity: 1 }],
    })
    vi.mocked(identifyMovie).mockResolvedValue({ ...MOVIE, title: 'Broadchurch', identified: true, setAsideAs: null, mediaType: 'tv' })
    renderPage()

    expect(await screen.findByText('Which series is this?')).not.toBeNull()
    const groups = await screen.findAllByRole('region', { name: /^(Films|TV series)$/ })
    expect(groups.map((group) => group.getAttribute('aria-label'))).toEqual(['TV series', 'Films'])
    expect(screen.queryByText('Set aside as not a film')).toBeNull()

    // TMDB numbers films and series separately: the same number, chosen as the series.
    fireEvent.click(screen.getByRole('button', { name: 'This is it: Broadchurch, the TV series' }))
    await waitFor(() => expect(identifyMovie).toHaveBeenCalledWith(MOVIE_ID, 990, 'tv'))
  })

  it('says a title set aside as not a film has no match, and can still be identified', async () => {
    vi.mocked(fetchMovie).mockResolvedValue({ ...MOVIE, title: 'A Concert', identified: false, setAsideAs: 'not_film', mediaType: 'other', overview: null })
    vi.mocked(fetchCandidates).mockResolvedValue({ movieId: MOVIE_ID, title: 'A Concert', query: 'A Concert', candidates: [], seriesCandidates: [] })
    renderPage()

    expect(await screen.findByText('Set aside as not a film')).not.toBeNull()
    expect(screen.queryByText('Which film is this?')).toBeNull()
    expect(fetchCandidates).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Identify it' }))
    expect(await screen.findByText('Which film is this?')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(screen.queryByText('Which film is this?')).toBeNull())
  })

  it('still asks which film it is when nothing set it aside', async () => {
    vi.mocked(fetchMovie).mockResolvedValue({ ...MOVIE, identified: false, setAsideAs: null })
    vi.mocked(fetchCandidates).mockResolvedValue({ movieId: MOVIE_ID, title: 'The Red Shoes', query: 'The Red Shoes', candidates: [], seriesCandidates: [] })
    renderPage()

    expect(await screen.findByText('Which film is this?')).not.toBeNull()
    expect(screen.queryByText('Set aside as not a film')).toBeNull()
  })

  it('shows a series no Letterboxd link and no price alert, which are films\' (Batch Y3)', async () => {
    vi.mocked(fetchMovie).mockResolvedValue({ ...MOVIE, title: 'Band of Brothers', identified: true, mediaType: 'tv' })
    renderPage()

    expect(await screen.findByRole('button', { name: /Correct match/ })).not.toBeNull()
    expect(screen.queryByRole('link', { name: /Letterboxd/ })).toBeNull()
  })
})
