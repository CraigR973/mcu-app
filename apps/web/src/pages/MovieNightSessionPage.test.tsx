// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MovieNightSessionPage from './MovieNightSessionPage'

const CRAIG = '11111111-1111-4111-8111-111111111111'
const MARK = '22222222-2222-4222-8222-222222222222'

const mocks = vi.hoisted(() => ({
  castMovieNightVote: vi.fn(),
  fetchMovieNight: vi.fn(),
  fetchMovieNightCandidates: vi.fn(),
  sendMovieNight: vi.fn(),
  streamMovieNightEvents: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  ...mocks,
  posterUrl: (path: string | null) => path ?? '/placeholder-poster.svg',
}))

vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: CRAIG, displayName: 'Craig', role: 'admin', hasPin: true, onboardingCompleted: true } }),
}))

const SESSION_ID = '3f2504e0-4f89-41d3-9a0c-0305e82c3401'
const MOVIE_ID = '3f2504e0-4f89-41d3-9a0c-0305e82c3402'
const SUGGESTION_ID = '9f1d2a6c-4c1e-4f6a-9d3b-8a2c7e5b1f04'
const VOTED_ID = '9f1d2a6c-4c1e-4f6a-9d3b-8a2c7e5b1f05'

async function* noEvents() {
  yield* []
}

const NIGHT = {
  id: SESSION_ID,
  status: 'open',
  filters: {},
  inviteToken: 'long-private-invite-token',
  invitePath: '/movie-night/join/long-private-invite-token',
  participantCount: 1,
  createdAt: '2026-09-23T18:00:00Z',
  endedAt: null,
  people: [{ id: CRAIG, displayName: 'Craig', invited: false }],
  invitable: [{ id: MARK, displayName: 'Mark' }],
}

const RED_SHOES = {
  suggestionId: SUGGESTION_ID,
  movieId: MOVIE_ID,
  tmdbId: null,
  title: 'The Red Shoes',
  year: 1948,
  posterPath: null,
  overview: 'A ballerina is torn between art and life.',
  runtimeMinutes: 135,
  genres: ['Drama'],
  cast: ['Moira Shearer'],
  suggestedBy: null,
  streamingOn: [],
  watchedBy: [],
  myVote: null,
}

function renderPage(withNearbyInput = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/movie-night/${SESSION_ID}`]}>
        {withNearbyInput ? <input aria-label="Nearby editor" /> : null}
        <Routes>
          <Route path="/movie-night/:id" element={<MovieNightSessionPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  mocks.fetchMovieNight.mockReset().mockResolvedValue(NIGHT)
  mocks.fetchMovieNightCandidates.mockReset().mockResolvedValue({
    // Batch S7: a card is a *suggestion*, and `myVote: null` is "not swiped yet", which is
    // what puts it in the deck.
    items: [
      RED_SHOES,
      { ...RED_SHOES, suggestionId: VOTED_ID, movieId: null, tmdbId: 11050, title: 'The Card Player', suggestedBy: 'Mark', streamingOn: ['MUBI'], myVote: true },
    ],
    total: 2,
  })
  mocks.castMovieNightVote.mockReset().mockResolvedValue({ recorded: true, match: null })
  mocks.sendMovieNight.mockReset().mockResolvedValue({
    ...NIGHT,
    participantCount: 2,
    people: [...NIGHT.people, { id: MARK, displayName: 'Mark', invited: true }],
    invitable: [],
  })
  mocks.streamMovieNightEvents.mockReset().mockImplementation(() => noEvents())
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('MovieNightSessionPage', () => {
  it('renders a failed shortlist request as an error rather than an empty list', async () => {
    mocks.fetchMovieNightCandidates.mockRejectedValueOnce(new Error('The shortlist service is unavailable.'))
    renderPage()

    expect(await screen.findByText('The shortlist service is unavailable.')).not.toBeNull()
    expect(screen.queryByText('No films on the list yet')).toBeNull()
  })

  it('opens on the shortlist, with your own vote on each film — Batch T4, snag 10b', async () => {
    renderPage()

    const list = within(await screen.findByRole('region', { name: /Tonight's shortlist/ }))
    expect(list.getByText('The Red Shoes')).not.toBeNull()
    expect(list.getByText('Not voted')).not.toBeNull()
    expect(list.getByText('Added')).not.toBeNull()
    expect(list.getByText(/Suggested by Mark · on MUBI/)).not.toBeNull()
    expect(list.getByRole('link', { name: /The Card Player/ }).getAttribute('href')).toBe('/films/tmdb/11050')
    expect(screen.getByRole('button', { name: 'Start swiping (1)' })).not.toBeNull()
    // The deck is one tap away, not the first thing shown.
    expect(screen.queryByRole('button', { name: 'Add' })).toBeNull()
  })

  it('says "Skip" and "Add" in the deck — snag 10e', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Start swiping (1)' }))

    fireEvent.click(screen.getByRole('button', { name: 'Add' }))

    await waitFor(() => expect(mocks.castMovieNightVote).toHaveBeenCalledWith(SESSION_ID, SUGGESTION_ID, true))
    expect(screen.queryByRole('button', { name: 'Like' })).toBeNull()
  })

  it('leaves arrow keys with an editable field and votes only from the deck', async () => {
    renderPage(true)
    fireEvent.click(await screen.findByRole('button', { name: 'Start swiping (1)' }))
    expect(await screen.findByRole('group', { name: /The Red Shoes/ })).not.toBeNull()

    const input = screen.getByLabelText('Nearby editor')
    input.focus()
    fireEvent.keyDown(input, { key: 'ArrowRight' })
    expect(mocks.castMovieNightVote).not.toHaveBeenCalled()

    fireEvent.keyDown(window, { key: 'ArrowRight' })
    await waitFor(() => {
      // Batch S7: **a vote is cast on a suggestion, not on a film.**
      expect(mocks.castMovieNightVote).toHaveBeenCalledWith(SESSION_ID, SUGGESTION_ID, true)
    })
  })

  it('does not vote from the list with an arrow key', async () => {
    renderPage()
    await screen.findByRole('region', { name: /Tonight's shortlist/ })

    fireEvent.keyDown(window, { key: 'ArrowRight' })

    expect(mocks.castMovieNightVote).not.toHaveBeenCalled()
  })

  it('sends the night to the other person in one tap — snag 11', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Send to Mark' }))

    await waitFor(() => expect(mocks.sendMovieNight).toHaveBeenCalledWith(SESSION_ID, [MARK]))
    expect(await screen.findByText('Sent to Mark')).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Send to Mark' })).toBeNull()
  })

  it('shares the link through the phone’s share sheet', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { ...navigator, share })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Share link' }))

    await waitFor(() =>
      expect(share).toHaveBeenCalledWith(expect.objectContaining({ url: `${window.location.origin}${NIGHT.invitePath}` })),
    )
  })
})
