// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
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
  subCategory: 'Criterion Collection',
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
  it('opens on owned copies and surfaces the collector edition, label and shelf', async () => {
    renderPage()

    expect(await screen.findByText('Criterion Collection')).not.toBeNull()
    expect(screen.getByText('Collector edition')).not.toBeNull()
    expect(screen.getByText('Release label')).not.toBeNull()
    expect(screen.getByText('The Criterion Collection')).not.toBeNull()
    expect(screen.getByText('Front 2nd shelf')).not.toBeNull()
    expect(screen.getByRole('tab', { name: /Owned copies/ }).getAttribute('aria-selected')).toBe('true')
  })

  it('reports a copy request failure instead of claiming there are no copies', async () => {
    vi.mocked(fetchCopies).mockRejectedValueOnce(new Error('Copies API unavailable'))
    renderPage()

    expect(await screen.findByText('Could not load the owned copies')).not.toBeNull()
    expect(screen.getByText('Copies API unavailable')).not.toBeNull()
    expect(screen.queryByText('No live copies in the collection')).toBeNull()
  })
})
