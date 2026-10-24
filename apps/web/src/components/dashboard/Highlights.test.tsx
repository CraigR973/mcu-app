// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Highlights as Data } from '@/lib/api'

const { fetchHighlightsMock } = vi.hoisted(() => ({ fetchHighlightsMock: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchHighlights: fetchHighlightsMock,
}))

import { Highlights } from './Highlights'

const HEAT = { movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3401', title: 'Heat', year: 1995, posterPath: null }
const ALIEN = { movieId: '3f2504e0-4f89-41d3-9a0c-0305e82c3402', title: 'Alien', year: 1979, posterPath: null }

const FULL: Data = {
  topRated: {
    items: [
      { ...HEAT, ratings: [{ personName: 'Craig', rating: 5 }] },
      { ...ALIEN, ratings: [{ personName: 'Craig', rating: 4.5 }] },
    ],
    ratedBy: ['Craig'],
    notRatedBy: ['Mark'],
  },
  mostRewatched: [
    { ...ALIEN, viewings: 3, byPerson: [{ personName: 'Craig', viewings: 2 }, { personName: 'Mark', viewings: 1 }] },
  ],
  mostValuable: [
    {
      ...HEAT,
      formatCode: '4k_uhd',
      price: '34.99',
      currency: 'GBP',
      basis: 'current asking prices',
      sampleSize: 7,
      valueBasis: 'used',
      factor: null,
      low: '29.99',
      high: '44.00',
      valuedAs: 'as used copies',
      checkedAt: '2026-09-26T03:00:00Z',
      copies: 2,
    },
  ],
  // V5's rows alone; V9's fourth is tested below.
  bestReviewed: [],
}

const EMPTY: Data = {
  topRated: { items: [], ratedBy: [], notRatedBy: ['Craig', 'Mark'] },
  mostRewatched: [],
  mostValuable: [],
  bestReviewed: [],
}

function renderPanel(data: Data | Error) {
  if (data instanceof Error) fetchHighlightsMock.mockRejectedValue(data)
  else fetchHighlightsMock.mockResolvedValue(data)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Highlights />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Highlights on Home — Batch V5', () => {
  it('shows the remaining short poster rows, each film opening its page', async () => {
    renderPanel(FULL)

    // Since W2 each row is a section of Home in its own right, and the "Highlights" heading
    // over them has gone (#249: "make all the sections look like highlights").
    expect(await screen.findByRole('region', { name: 'Most rewatched' })).not.toBeNull()
    expect(screen.queryByRole('region', { name: 'Top rated' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Highlights' })).toBeNull()
    for (const [row, films] of [
      ['Most rewatched', ['Alien']],
      ['Most valuable discs', ['Heat']],
    ] as const) {
      const region = within(screen.getByRole('region', { name: row }))
      expect(region.getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual(
        films.map((title) => `/movies/${title === 'Heat' ? HEAT.movieId : ALIEN.movieId}`),
      )
    }
    expect(fetchHighlightsMock).toHaveBeenCalledTimes(1)
  })

  it('leaves Top rated and the ratings detail off Home — AA1', async () => {
    renderPanel(FULL)
    await screen.findByRole('region', { name: 'Most rewatched' })

    expect(screen.queryByRole('region', { name: 'Top rated' })).toBeNull()
    expect(screen.queryByText('Rated 4½ or 5 stars by Craig. Mark has not rated any films.')).toBeNull()
  })

  it('counts rewatches across both diaries, saying whose', async () => {
    renderPanel(FULL)
    const row = within(await screen.findByRole('region', { name: 'Most rewatched' }))

    expect(row.getByText(/3 viewings/)).not.toBeNull()
    expect(row.getByText('Craig 2 · Mark 1')).not.toBeNull()
  })

  it('shows each disc at its stored value, with its basis and listings', async () => {
    renderPanel(FULL)
    const row = within(await screen.findByRole('region', { name: 'Most valuable discs' }))

    expect(row.getByText('At their stored value as used copies: eBay current asking prices, checked 26 Sep 2026.')).not.toBeNull()
    expect(row.getByText(/£34\.99 · 4K UHD/)).not.toBeNull()
    // Batch X6: what stands behind the value, its listings and their range.
    expect(row.getByText('7 used listings, £29.99–£44.00 · 2 copies')).not.toBeNull()
  })

  it('leaves out a row with nothing in it', async () => {
    renderPanel({ ...FULL, mostRewatched: [] })

    expect(await screen.findByRole('region', { name: 'Most valuable discs' })).not.toBeNull()
    expect(screen.queryByRole('region', { name: 'Most rewatched' })).toBeNull()
    expect(screen.queryByText('Most rewatched')).toBeNull()
    expect(screen.getByRole('region', { name: 'Most valuable discs' })).not.toBeNull()
  })

  it('leaves out the whole panel when every row is empty', async () => {
    renderPanel(EMPTY)
    await vi.waitFor(() => expect(fetchHighlightsMock).toHaveBeenCalled())
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(screen.queryAllByRole('region')).toHaveLength(0)
    expect(screen.queryAllByRole('heading')).toHaveLength(0)
  })

  it('says so when the highlights cannot be read', async () => {
    renderPanel(new Error('The highlights service is down.'))

    expect(await screen.findByText('Highlights are unavailable')).not.toBeNull()
    expect(screen.getByText('The highlights service is down.')).not.toBeNull()
  })
})

describe('Highlights on Home — Batch V9, the best reviewed', () => {
  const REVIEWED: Data = {
    ...FULL,
    bestReviewed: [
      { ...ALIEN, overall: 4.5, outOf: 5, formatCode: '4k_uhd', strength: 'picture', scores: [{ heading: 'Video 4K', score: 5 }, { heading: 'Audio', score: 4 }] },
      { ...HEAT, overall: 4, outOf: 5, formatCode: 'blu_ray', strength: 'sound', scores: [{ heading: 'Video 2K', score: 3 }, { heading: 'Audio', score: 4.5 }] },
    ],
  }

  it('ranks owned films by Blu-ray.com\'s overall score, each opening its page', async () => {
    renderPanel(REVIEWED)
    const row = within(await screen.findByRole('region', { name: 'Best discs' }))

    expect(row.getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual([
      `/movies/${ALIEN.movieId}`,
      `/movies/${HEAT.movieId}`,
    ])
    expect(row.getByText("Blu-ray.com scores the disc's picture, sound and extras, not the film.")).not.toBeNull()
    expect(row.getByText('Strongest for picture')).not.toBeNull()
    expect(row.getByText('Strongest for sound')).not.toBeNull()
    expect(row.getByText('4.5/5 · 4K UHD')).not.toBeNull()
    expect(row.getByText('4.0/5 · Blu-ray')).not.toBeNull()
    expect(row.getAllByText('Scores')).toHaveLength(2)
    expect(row.getByText('Video 4K 5.0 · Audio 4.0')).not.toBeNull()
  })

  it('follows the most valuable discs', async () => {
    renderPanel(REVIEWED)
    await screen.findByRole('region', { name: 'Best discs' })

    // Level 2 since W2, when the rows became peers of Home's other sections.
    const titles = screen.getAllByRole('heading', { level: 2 }).map((heading) => heading.textContent)
    expect(titles).toEqual(['Most rewatched', 'Most valuable discs', 'Best discs'])
  })

  it('is left out until a review has been read', async () => {
    renderPanel(FULL)
    await screen.findByRole('region', { name: 'Most rewatched' })

    expect(screen.queryByRole('region', { name: 'Best discs' })).toBeNull()
  })
})

