// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MovieNightSessionPage from './MovieNightSessionPage'

const mocks = vi.hoisted(() => ({
  castMovieNightVote: vi.fn(),
  fetchMovieNight: vi.fn(),
  fetchMovieNightCandidates: vi.fn(),
  streamMovieNightEvents: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  ...mocks,
  posterUrl: (path: string | null) => path ?? '/placeholder-poster.svg',
}))

const SESSION_ID = '3f2504e0-4f89-41d3-9a0c-0305e82c3401'
const MOVIE_ID = '3f2504e0-4f89-41d3-9a0c-0305e82c3402'
const SUGGESTION_ID = '9f1d2a6c-4c1e-4f6a-9d3b-8a2c7e5b1f04'

async function* noEvents() {
  yield* []
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
  mocks.fetchMovieNight.mockReset().mockResolvedValue({
    id: SESSION_ID,
    status: 'open',
    filters: {},
    inviteToken: 'long-private-invite-token',
    invitePath: '/movie-night/join/long-private-invite-token',
    participantCount: 2,
    createdAt: '2026-09-10T12:00:00Z',
    endedAt: null,
  })
  mocks.fetchMovieNightCandidates.mockReset().mockResolvedValue({
    // Batch S7: a card is a *suggestion* now, and carries what it takes to decide without
    // opening another screen — `myVote: null` is "not swiped yet", which is what puts it
    // in the deck.
    items: [{
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
    }],
    total: 1,
  })
  mocks.castMovieNightVote.mockReset().mockResolvedValue({ recorded: true, match: null })
  mocks.streamMovieNightEvents.mockReset().mockImplementation(() => noEvents())
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('MovieNightSessionPage', () => {
  it('renders a failed shortlist request as an error rather than an empty deck', async () => {
    mocks.fetchMovieNightCandidates.mockRejectedValueOnce(new Error('The shortlist service is unavailable.'))
    renderPage()

    expect(await screen.findByText('The shortlist service is unavailable.')).not.toBeNull()
    expect(screen.queryByText('No films match this screening')).toBeNull()
    expect(screen.queryByText('That is the whole deck')).toBeNull()
  })

  it('leaves arrow keys with an editable field and votes only from the page shortcut', async () => {
    renderPage(true)
    expect(await screen.findByText('The Red Shoes')).not.toBeNull()

    const input = screen.getByLabelText('Nearby editor')
    input.focus()
    fireEvent.keyDown(input, { key: 'ArrowRight' })
    expect(mocks.castMovieNightVote).not.toHaveBeenCalled()

    fireEvent.keyDown(window, { key: 'ArrowRight' })
    await waitFor(() => {
      // Batch S7: **a vote is cast on a suggestion, not on a film.** That is what lets
      // everyone vote on anyone's suggestion, and what lets a film outside the Archive —
      // which has no `movies` row — be voted on at all.
      expect(mocks.castMovieNightVote).toHaveBeenCalledWith(SESSION_ID, SUGGESTION_ID, true)
    })
  })
})
