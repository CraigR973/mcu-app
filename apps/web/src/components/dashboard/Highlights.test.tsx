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
      checkedAt: '2026-09-26T03:00:00Z',
      copies: 2,
    },
  ],
}

const EMPTY: Data = { topRated: { items: [], ratedBy: [], notRatedBy: ['Craig', 'Mark'] }, mostRewatched: [], mostValuable: [] }

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
  it('shows three short poster rows, each film opening its page', async () => {
    renderPanel(FULL)

    expect(await screen.findByRole('heading', { name: 'Highlights' })).not.toBeNull()
    for (const [row, films] of [
      ['Top rated', ['Heat', 'Alien']],
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

  it("says whose ratings they are, and who does not rate (#159)", async () => {
    renderPanel(FULL)
    const top = within(await screen.findByRole('region', { name: 'Top rated' }))

    expect(top.getByText('Rated 4½ or 5 stars by Craig. Mark has not rated any films.')).not.toBeNull()
    expect(top.getByText('★ 5 Craig')).not.toBeNull()
    expect(top.getByText('★ 4½ Craig')).not.toBeNull()
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

    expect(row.getByText('At their stored value: eBay current asking prices, checked 26 Sep 2026.')).not.toBeNull()
    expect(row.getByText(/£34\.99 · 4K UHD/)).not.toBeNull()
    expect(row.getByText('7 listings · 2 copies')).not.toBeNull()
  })

  it('leaves out a row with nothing in it', async () => {
    renderPanel({ ...FULL, mostRewatched: [] })

    expect(await screen.findByRole('region', { name: 'Top rated' })).not.toBeNull()
    expect(screen.queryByRole('region', { name: 'Most rewatched' })).toBeNull()
    expect(screen.queryByText('Most rewatched')).toBeNull()
    expect(screen.getByRole('region', { name: 'Most valuable discs' })).not.toBeNull()
  })

  it('leaves out the whole panel when every row is empty', async () => {
    renderPanel(EMPTY)
    await vi.waitFor(() => expect(fetchHighlightsMock).toHaveBeenCalled())
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(screen.queryByRole('heading', { name: 'Highlights' })).toBeNull()
  })

  it('says so when the highlights cannot be read', async () => {
    renderPanel(new Error('The highlights service is down.'))

    expect(await screen.findByText('Highlights are unavailable')).not.toBeNull()
    expect(screen.getByText('The highlights service is down.')).not.toBeNull()
  })
})
