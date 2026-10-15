// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { IdentifyDoubts, IdentifyOverview, IdentifyQueue, RecentIdentifications } from '@/lib/api'

const {
  overviewMock,
  queueMock,
  recentMock,
  searchMock,
  identifyMock,
  asideMock,
  skipMock,
  undoMock,
  doubtsMock,
  keepMock,
  correctMock,
} = vi.hoisted(() => ({
  doubtsMock: vi.fn(),
  keepMock: vi.fn(),
  correctMock: vi.fn(),
  overviewMock: vi.fn(),
  queueMock: vi.fn(),
  recentMock: vi.fn(),
  searchMock: vi.fn(),
  identifyMock: vi.fn(),
  asideMock: vi.fn(),
  skipMock: vi.fn(),
  undoMock: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchIdentifyOverview: overviewMock,
  fetchIdentifyQueue: queueMock,
  fetchRecentIdentifications: recentMock,
  searchIdentify: searchMock,
  identifyFilm: identifyMock,
  setFilmAside: asideMock,
  skipFilm: skipMock,
  undoIdentification: undoMock,
  fetchIdentifyDoubts: doubtsMock,
  keepIdentification: keepMock,
  correctIdentification: correctMock,
}))

import IdentifyFilmsPage from './IdentifyFilmsPage'

const FILM = '00000000-0000-4000-8000-000000000031'
const HELD = '00000000-0000-4000-8000-000000000032'
const ACTION = '00000000-0000-4000-8000-000000000033'

const OVERVIEW: IdentifyOverview = {
  unidentified: 212,
  waiting: 178,
  setAsideTv: 33,
  setAsideNotFilm: 1,
  skipped: 0,
  identified: 145,
  run: null,
}

const QUEUE: IdentifyQueue = {
  total: 178,
  items: [
    {
      movieId: FILM,
      title: 'Dunkirk',
      discs: [{ label: '4K · Front' }],
      watches: 0,
      note: 'TMDB holds 3 other films of this title (1958, 2004, 2017), and nothing in the title or the grouping says which.',
      proposedTmdbId: 374720,
      candidates: [
        {
          tmdbId: 374720,
          title: 'Dunkirk',
          year: 2017,
          posterPath: null,
          overview: '',
          votes: 18007,
          notes: ['18,007 TMDB votes'],
          inCollection: null,
        },
        {
          tmdbId: 36265,
          title: 'Dunkirk',
          year: 1958,
          posterPath: null,
          overview: '',
          votes: 77,
          notes: ['77 TMDB votes'],
          inCollection: { movieId: HELD, title: 'Dunkirk', year: 1958, discs: 1, watches: 0 },
        },
      ],
    },
  ],
}

const RECENT: RecentIdentifications = {
  items: [
    {
      actionId: ACTION,
      at: '2026-09-25T15:00:00+00:00',
      by: null,
      movieId: '00000000-0000-4000-8000-000000000034',
      replaced: 'Peepiing Tom',
      title: 'Peeping Tom',
      year: 1960,
      how: 'auto',
      merged: false,
      undone: false,
    },
  ],
}

const DOUBT_ID = '00000000-0000-4000-8000-000000000035'
const DOUBTED = '00000000-0000-4000-8000-000000000036'

const DOUBTS: IdentifyDoubts = {
  total: 1,
  items: [
    {
      doubtId: DOUBT_ID,
      movieId: DOUBTED,
      title: 'The Bridge on the River Kwai',
      year: 2007,
      tmdbId: 501,
      posterPath: null,
      source: 'specs',
      note: 'Blu-ray.com’s disc page for “The Bridge on the River Kwai” is a 1957 film, and this film is identified as 2007. The copy may be the 1957 film.',
      evidence: ['Blu-ray.com’s disc page for “The Bridge on the River Kwai” is a 1957 film, and this film is identified as 2007. The copy may be the 1957 film.'],
      discs: [{ label: '4K · Alec Guinness' }],
      copies: 1,
      watches: 0,
      collectionItemId: null,
      candidates: [],
      proposedTmdbId: null,
      searchHint: 'The Bridge on the River Kwai 1957',
      raisedAt: '2026-10-15T02:30:00+00:00',
    },
  ],
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <IdentifyFilmsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('IdentifyFilmsPage', () => {
  beforeEach(() => {
    overviewMock.mockResolvedValue(OVERVIEW)
    queueMock.mockResolvedValue(QUEUE)
    recentMock.mockResolvedValue(RECENT)
    identifyMock.mockResolvedValue({ movieId: FILM, outcome: 'identified', title: 'Dunkirk' })
    asideMock.mockResolvedValue({ movieId: FILM, outcome: 'set_aside', title: '' })
    skipMock.mockResolvedValue({ movieId: FILM, outcome: 'skipped', title: '' })
    undoMock.mockResolvedValue({ movieId: FILM, outcome: 'waiting', title: 'Peepiing Tom' })
    searchMock.mockResolvedValue({ query: 'Dunkirk 2017', candidates: [] })
    doubtsMock.mockResolvedValue({ items: [], total: 0 })
    keepMock.mockResolvedValue({ movieId: DOUBTED, outcome: 'kept', title: '' })
    correctMock.mockResolvedValue({ movieId: DOUBTED, outcome: 'identified', title: 'The Bridge on the River Kwai' })
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('says how many films wait and why this one does', async () => {
    renderPage()

    expect(await screen.findByText('178 of 212 unmatched films wait for you')).toBeTruthy()
    expect(screen.getByText(/nothing in the title or the grouping says which/)).toBeTruthy()
    expect(screen.getByText('4K · Front')).toBeTruthy()
  })

  it('picks a film in one tap', async () => {
    renderPage()
    const card = await screen.findByRole('article', { name: 'Dunkirk' })

    fireEvent.click(within(card).getByRole('button', { name: /This is it/ }))

    await vi.waitFor(() => expect(identifyMock).toHaveBeenCalledWith(FILM, 374720, { merge: false, searched: false }))
  })

  it('shows the film a choice would merge into, and says merge when that one is chosen', async () => {
    renderPage()
    const card = await screen.findByRole('article', { name: 'Dunkirk' })

    expect(within(card).getByText(/You already have this as/)).toBeTruthy()
    fireEvent.click(within(card).getByRole('button', { name: /Merge into this film/ }))

    await vi.waitFor(() => expect(identifyMock).toHaveBeenCalledWith(FILM, 36265, { merge: true, searched: false }))
  })

  it('sets a film aside as TV, as not a film, or skips it', async () => {
    renderPage()
    const card = await screen.findByRole('article', { name: 'Dunkirk' })

    fireEvent.click(within(card).getByRole('button', { name: /TV series/ }))
    await vi.waitFor(() => expect(asideMock).toHaveBeenCalledWith(FILM, 'tv'))
    fireEvent.click(within(card).getByRole('button', { name: /Not a film/ }))
    await vi.waitFor(() => expect(asideMock).toHaveBeenCalledWith(FILM, 'not_film'))
    fireEvent.click(within(card).getByRole('button', { name: /Skip/ }))
    await vi.waitFor(() => expect(skipMock).toHaveBeenCalledWith(FILM))
  })

  it('searches again with a corrected title', async () => {
    renderPage()
    const card = await screen.findByRole('article', { name: 'Dunkirk' })
    const input = within(card).getByRole('textbox', { name: 'Search TMDB again for Dunkirk' })

    fireEvent.change(input, { target: { value: 'Dunkirk 2017' } })
    fireEvent.click(within(card).getByRole('button', { name: /Search/ }))

    await vi.waitFor(() => expect(searchMock).toHaveBeenCalledWith(FILM, 'Dunkirk 2017'))
    expect(await within(card).findByText(/No films found/)).toBeTruthy()
  })

  it('undoes a recent identification', async () => {
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: /Undo/ }))

    await vi.waitFor(() => expect(undoMock).toHaveBeenCalledWith(ACTION))
    expect(screen.getByText('Peepiing Tom')).toBeTruthy()
  })

  describe('films in doubt (Batch X9)', () => {
    beforeEach(() => {
      doubtsMock.mockResolvedValue(DOUBTS)
    })

    it('shows an identified film in doubt with what disagrees, and keeps it in one tap', async () => {
      renderPage()
      const card = await screen.findByRole('article', { name: 'The Bridge on the River Kwai (2007)' })

      expect(screen.getByRole('heading', { name: 'In doubt (1)' })).toBeTruthy()
      expect(within(card).getByText(/is a 1957 film, and this film is identified as 2007/)).toBeTruthy()
      expect(within(card).getByText('4K · Alec Guinness')).toBeTruthy()
      fireEvent.click(within(card).getByRole('button', { name: /It’s right/ }))

      await vi.waitFor(() => expect(keepMock).toHaveBeenCalledWith(DOUBT_ID))
    })

    it('searches for the film the page names, never offers the film it already is, and corrects to another', async () => {
      searchMock.mockResolvedValue({
        query: 'The Bridge on the River Kwai 1957',
        candidates: [
          { tmdbId: 501, title: 'The Bridge on the River Kwai', year: 2007, posterPath: null, overview: '', votes: 3, notes: [], inCollection: null },
          { tmdbId: 826, title: 'The Bridge on the River Kwai', year: 1957, posterPath: null, overview: '', votes: 3500, notes: [], inCollection: null },
        ],
      })
      renderPage()
      const card = await screen.findByRole('article', { name: 'The Bridge on the River Kwai (2007)' })
      const input = within(card).getByRole('textbox', { name: 'Search TMDB for the film The Bridge on the River Kwai may be' })

      expect((input as HTMLInputElement).value).toBe('The Bridge on the River Kwai 1957')
      fireEvent.click(within(card).getByRole('button', { name: /Search/ }))
      const results = await within(card).findByRole('list', { name: 'Search results for The Bridge on the River Kwai' })

      expect(within(results).getAllByRole('listitem')).toHaveLength(1)
      fireEvent.click(within(results).getByRole('button', { name: /This is it/ }))
      await vi.waitFor(() => expect(correctMock).toHaveBeenCalledWith(DOUBT_ID, 826, { merge: false, searched: true }))
    })

    it('counts the films in doubt in the overview', async () => {
      overviewMock.mockResolvedValue({ ...OVERVIEW, inDoubt: 7 })
      renderPage()

      const overview = await screen.findByRole('region', { name: 'Where they stand' })
      expect(within(overview).getByText('Identified, in doubt')).toBeTruthy()
      expect(within(overview).getByText('7')).toBeTruthy()
    })
  })
})
