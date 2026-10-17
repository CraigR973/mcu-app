// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MoveCopyPanel } from './MoveCopyPanel'

const { searchMock, moveMock } = vi.hoisted(() => ({ searchMock: vi.fn(), moveMock: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  searchIdentify: searchMock,
  moveCopy: moveMock,
}))

const ITEM = '00000000-0000-4000-8000-000000000051'
const FILM = '00000000-0000-4000-8000-000000000052'
const OTHER = '00000000-0000-4000-8000-000000000053'

function renderPanel(onMoved = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MoveCopyPanel itemId={ITEM} movieId={FILM} filmTitle="French Connection II" onMoved={onMoved} />
    </QueryClientProvider>,
  )
  return onMoved
}

describe('MoveCopyPanel (Batch X9)', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('searches for the film the copy is, never offers the film it is on, and moves it alone', async () => {
    searchMock.mockResolvedValue({
      query: 'The French Connection',
      candidates: [
        { tmdbId: 10711, title: 'French Connection II', year: 1975, posterPath: null, overview: '', votes: 486, notes: [], inCollection: { movieId: FILM, title: 'French Connection II', year: 1975, discs: 2, watches: 1 } },
        { tmdbId: 1051, title: 'The French Connection', year: 1971, posterPath: null, overview: '', votes: 2400, notes: [], inCollection: { movieId: OTHER, title: 'The French Connection', year: 1971, discs: 0, watches: 0 } },
      ],
    })
    const moved = { movieId: OTHER, title: 'The French Connection', year: 1971, created: false, actionId: '00000000-0000-4000-8000-000000000054' }
    moveMock.mockResolvedValue(moved)
    const onMoved = renderPanel()

    fireEvent.click(screen.getByRole('button', { name: /This copy is another film/ }))
    const input = screen.getByRole('textbox', { name: 'Search TMDB for the film this copy is' })
    expect((input as HTMLInputElement).value).toBe('French Connection II')
    fireEvent.change(input, { target: { value: 'The French Connection' } })
    fireEvent.click(screen.getByRole('button', { name: /Search/ }))
    const offered = await screen.findByRole('list', { name: 'Films this copy may be' })

    expect(within(offered).getAllByRole('listitem')).toHaveLength(1)
    expect(within(offered).getByText('Already in the collection')).toBeTruthy()
    fireEvent.click(within(offered).getByRole('button', { name: 'Move this copy here' }))

    await vi.waitFor(() => expect(moveMock).toHaveBeenCalledWith(ITEM, 1051))
    await vi.waitFor(() => expect(onMoved).toHaveBeenCalled())
    expect(onMoved.mock.calls[0]?.[0]).toEqual(moved)
  })

  it('says why a move was refused', async () => {
    searchMock.mockResolvedValue({
      query: 'Rome',
      candidates: [{ tmdbId: 7, title: 'Rome', year: 1972, posterPath: null, overview: '', votes: 3, notes: [], inCollection: null }],
    })
    moveMock.mockRejectedValue(new Error("'Rome' is in the Trash. Restore it before moving a copy to it."))
    renderPanel()

    fireEvent.click(screen.getByRole('button', { name: /This copy is another film/ }))
    fireEvent.click(screen.getByRole('button', { name: /Search/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Move this copy here' }))

    expect(await screen.findByRole('alert')).toBeTruthy()
  })
})

describe('MoveCopyPanel (Batch Y5)', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  function renderFromDoubt(title: string) {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MoveCopyPanel itemId={ITEM} movieId={FILM} filmTitle={title} onMoved={vi.fn()} startOpen />
      </QueryClientProvider>,
    )
  }

  it('opens from a doubt already searched, and moves the copy to a series', async () => {
    searchMock.mockResolvedValue({
      query: 'Tinker Tailor Soldier Spy (TV)',
      candidates: [
        { tmdbId: 49517, title: 'Tinker Tailor Soldier Spy', year: 2011, posterPath: null, overview: '', votes: 6000, notes: [], inCollection: { movieId: FILM, title: 'Tinker Tailor Soldier Spy', year: 2011, discs: 2, watches: 0 } },
      ],
      seriesCandidates: [
        { tmdbId: 35430, title: 'Tinker Tailor Soldier Spy', year: 1979, posterPath: null, overview: 'Smiley hunts the mole.', votes: 140, notes: [], inCollection: null, mediaType: 'tv' },
      ],
    })
    moveMock.mockResolvedValue({ movieId: OTHER, title: 'Tinker Tailor Soldier Spy', year: 1979, created: true, actionId: '00000000-0000-4000-8000-000000000055' })
    renderFromDoubt('Tinker Tailor Soldier Spy (TV)')

    const series = await screen.findByRole('list', { name: 'TV series this copy may be' })
    expect(searchMock).toHaveBeenCalledWith(FILM, 'Tinker Tailor Soldier Spy (TV)')
    // The film the copy is on is not offered, so only the series is.
    expect(screen.queryByRole('list', { name: 'Films this copy may be' })).toBeNull()
    expect(within(series).getByText(/TV series/)).toBeTruthy()
    expect(within(series).getByText('Smiley hunts the mole.')).toBeTruthy()
    fireEvent.click(within(series).getByRole('button', { name: 'Move this copy here' }))

    await vi.waitFor(() => expect(moveMock).toHaveBeenCalledWith(ITEM, 35430, undefined, 'tv'))
  })

  it('lists films and series under their own headings', async () => {
    searchMock.mockResolvedValue({
      query: 'Life',
      candidates: [{ tmdbId: 7, title: 'Life', year: 1999, posterPath: null, overview: '', votes: 300, notes: [], inCollection: null }],
      seriesCandidates: [{ tmdbId: 16946, title: 'Life', year: 2009, posterPath: null, overview: '', votes: 180, notes: [], inCollection: null, mediaType: 'tv' }],
    })
    renderFromDoubt('Life')

    expect(await screen.findByRole('list', { name: 'Films this copy may be' })).toBeTruthy()
    expect(screen.getByRole('list', { name: 'TV series this copy may be' })).toBeTruthy()
    expect(screen.getByText('Films')).toBeTruthy()
    expect(screen.getByText('TV series')).toBeTruthy()
  })
})
