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
    // Batch S7: a card is a *suggestion*, and `myVote: null` is "not voted yet". Since V3
    // there is no deck: every film is on the one list, with its own Add / Added control.
    items: [
      RED_SHOES,
      {
        ...RED_SHOES,
        suggestionId: VOTED_ID,
        movieId: null,
        tmdbId: 11050,
        title: 'The Card Player',
        suggestedBy: 'Mark',
        streamingOn: ['MUBI'],
        watchedBy: [{ personName: 'Mark', watchedAt: '2026-08-14' }],
        myVote: true,
      },
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

  it('opens on the shortlist, one Add / Added control per film — Batch V3 (#228)', async () => {
    renderPage()

    const list = within(await screen.findByRole('region', { name: /Tonight's shortlist/ }))
    expect(list.getByRole('button', { name: /The Red Shoes 1948/, expanded: false })).not.toBeNull()
    expect(list.getByText(/Suggested by Mark · on MUBI/)).not.toBeNull()
    // Your own vote, and only yours (#157): the film you added reads "Added", pressed.
    const add = list.getByRole('button', { name: 'Add The Red Shoes' })
    const added = list.getByRole('button', { name: 'Added The Card Player' })
    expect(add.getAttribute('aria-pressed')).toBe('false')
    expect(added.getAttribute('aria-pressed')).toBe('true')
    expect(list.getAllByRole('button', { name: /^Add(ed)? / })).toHaveLength(2)
  })

  it('has no deck: no "Start swiping", no Skip, no "N of M" count (#228)', async () => {
    // Retired with the deck: Phase 8.4's swipe-like UI and #207's arrow-key rule.
    renderPage()
    await screen.findByRole('region', { name: /Tonight's shortlist/ })

    expect(screen.queryByRole('button', { name: /Start swiping/ })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Skip' })).toBeNull()
    expect(screen.queryByRole('group', { name: /Swipe right/ })).toBeNull()
    expect(screen.queryByText(/^\d+ of \d+$/)).toBeNull()
  })

  it('votes for a film with Add, and takes the vote back with Added', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Add The Red Shoes' }))

    await waitFor(() => expect(mocks.castMovieNightVote).toHaveBeenCalledWith(SESSION_ID, SUGGESTION_ID, true))
    const added = await screen.findByRole('button', { name: 'Added The Red Shoes' })
    expect(added.getAttribute('aria-pressed')).toBe('true')

    // The API replaces a vote (`record_vote`), so taking it back is a vote of false.
    fireEvent.click(added)
    await waitFor(() => expect(mocks.castMovieNightVote).toHaveBeenLastCalledWith(SESSION_ID, SUGGESTION_ID, false))
    expect(await screen.findByRole('button', { name: 'Add The Red Shoes' })).not.toBeNull()
    expect(mocks.castMovieNightVote).toHaveBeenCalledTimes(2)
  })

  it("opens a film's details in its row when the film is tapped", async () => {
    renderPage()
    const film = await screen.findByRole('button', { name: /The Red Shoes/, expanded: false })
    expect(screen.queryByText('A ballerina is torn between art and life.')).toBeNull()

    fireEvent.click(film)

    expect(film.getAttribute('aria-expanded')).toBe('true')
    const details = within(document.getElementById(film.getAttribute('aria-controls') ?? '') as HTMLElement)
    expect(details.getByText('A ballerina is torn between art and life.')).not.toBeNull()
    expect(details.getByText('2h 15m · Drama')).not.toBeNull()
    expect(details.getByText('Moira Shearer')).not.toBeNull()
    expect(details.getByRole('link', { name: 'Open its page' }).getAttribute('href')).toBe(`/movies/${MOVIE_ID}`)
    // Opening a film is not a vote.
    expect(mocks.castMovieNightVote).not.toHaveBeenCalled()
  })

  it('says in the row who else has seen a film, when, and where it streams', async () => {
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: /The Card Player/, expanded: false }))

    expect(await screen.findByText(/Mark saw this on/)).not.toBeNull()
    expect(screen.getByText('MUBI', { exact: false, selector: 'p' })).not.toBeNull()
    expect(screen.getByRole('link', { name: 'Open its page' }).getAttribute('href')).toBe('/films/tmdb/11050')
  })

  it('announces a match from the list, once the vote completes one', async () => {
    mocks.castMovieNightVote.mockResolvedValueOnce({
      recorded: true,
      match: { movieId: MOVIE_ID, title: 'The Red Shoes', posterPath: null },
    })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Add The Red Shoes' }))

    const banner = await screen.findByRole('status')
    expect(within(banner).getByText("It's a match")).not.toBeNull()
    expect(within(banner).getByText('The Red Shoes')).not.toBeNull()
  })

  it('says so when a vote does not register, and leaves the film as it was', async () => {
    mocks.castMovieNightVote.mockRejectedValueOnce(new Error('The vote service is unavailable.'))
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Add The Red Shoes' }))

    expect(await screen.findByRole('alert')).not.toBeNull()
    expect(screen.getByText('The vote service is unavailable.')).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Add The Red Shoes' }).getAttribute('aria-pressed')).toBe('false')
  })

  it("keeps the other person's votes hidden when one arrives live (#157)", async () => {
    // The stream says only that *a* vote happened. Nothing on the list may move for it.
    mocks.streamMovieNightEvents.mockImplementation(async function* () {
      yield { kind: 'vote', suggestionId: SUGGESTION_ID }
    })
    renderPage()
    expect(await screen.findByRole('button', { name: 'Add The Red Shoes' })).not.toBeNull()
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(screen.getByRole('button', { name: 'Add The Red Shoes' }).getAttribute('aria-pressed')).toBe('false')
    expect(mocks.fetchMovieNightCandidates).toHaveBeenCalledTimes(1)
  })

  it('shows an ended night read-only', async () => {
    mocks.fetchMovieNight.mockResolvedValue({ ...NIGHT, status: 'ended', endedAt: '2026-09-23T22:00:00Z' })
    renderPage()

    const add = await screen.findByRole('button', { name: 'Add The Red Shoes' })
    await waitFor(() => expect((add as HTMLButtonElement).disabled).toBe(true))
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

  it('shows the match the session remembers, from the film, and hides it on Keep going — Batch X12a', async () => {
    mocks.fetchMovieNight.mockResolvedValue({
      ...NIGHT,
      match: { movieId: MOVIE_ID, title: 'The Exorcist', year: 1973, posterPath: '/exorcist.jpg' },
    })
    renderPage()

    expect(await screen.findByText("It's a match")).not.toBeNull()
    expect(screen.getByText('The Exorcist (1973)')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Keep going' }))
    await waitFor(() => expect(screen.queryByText("It's a match")).toBeNull())
  })

  it('shows no match banner when the session has none', async () => {
    renderPage()
    await screen.findByRole('region', { name: /Tonight's shortlist/ })
    expect(screen.queryByText("It's a match")).toBeNull()
  })
})
