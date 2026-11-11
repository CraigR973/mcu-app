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
  logMovieNight: vi.fn(),
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

    const list = within(await screen.findByRole('region', { name: /From the shelf/ }))
    expect(list.getByRole('button', { name: /The Red Shoes 1948/, expanded: false })).not.toBeNull()
    const suggested = within(screen.getByRole('region', { name: /^Suggested/ }))
    expect(suggested.getByText(/Suggested by Mark · on MUBI/)).not.toBeNull()
    // Your own vote, and only yours (#157): the film you added reads "Added", pressed.
    const add = list.getByRole('button', { name: 'Add The Red Shoes' })
    const added = suggested.getByRole('button', { name: 'Added The Card Player' })
    expect(add.getAttribute('aria-pressed')).toBe('false')
    expect(added.getAttribute('aria-pressed')).toBe('true')
    expect(list.getAllByRole('button', { name: /^Add(ed)? / })).toHaveLength(1)
    expect(suggested.getAllByRole('button', { name: /^Add(ed)? / })).toHaveLength(1)
  })

  it('has no deck: no "Start swiping", no Skip, no "N of M" count (#228)', async () => {
    // Retired with the deck: Phase 8.4's swipe-like UI and #207's arrow-key rule.
    renderPage()
    await screen.findByRole('region', { name: /From the shelf/ })

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
    await screen.findByRole('region', { name: /From the shelf/ })

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
    await screen.findByRole('region', { name: /From the shelf/ })
    expect(screen.queryByText("It's a match")).toBeNull()
  })
})


it('opens with Suggest a film, then people’s picks, then the films the night dealt — AE10', async () => {
  renderPage()
  await screen.findByRole('region', { name: /From the shelf/ })
  const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
  expect(headings[0]).toBe('Suggest a film')
  expect(headings[1]).toMatch(/^Suggested/)
  expect(headings[2]).toMatch(/^From the shelf/)
})


it('shows both people’s own watch and rating, shelf first, IMDb and a Letterboxd link', async () => {
  mocks.fetchMovieNightCandidates.mockResolvedValue({ items: [{
    ...RED_SHOES,
    people: [
      { personId: CRAIG, personName: 'Craig', lastWatchedAt: '2026-10-20', personalRating: 4.5 },
      { personId: MARK, personName: 'Mark', lastWatchedAt: null, personalRating: null },
    ],
    locations: [{ location: 'Front 2nd shelf', section: 'Front', shelf: '2nd' }],
    imdbId: 'tt0040725', imdbRating: 8.2, imdbVotes: 1234, imdbCheckedAt: '2026-10-25T02:00:00Z',
    streamingOn: ['Should be hidden'],
  }], total: 1 })
  renderPage()
  fireEvent.click(await screen.findByRole('button', { name: /The Red Shoes/, expanded: false }))
  const people = within(screen.getByRole('list', { name: 'Watch history and personal ratings' }))
  expect(people.getByText(/last watched 20 Oct 2026 · 4.5\/5/)).not.toBeNull()
  expect(people.getByText(/no watch logged · not rated/)).not.toBeNull()
  expect(screen.getByText('Front 2nd shelf')).not.toBeNull()
  expect(screen.queryByText('Should be hidden', { exact: false })).toBeNull()
  expect(screen.getAllByRole('link', { name: /^IMDb$/ }).map((link) => link.getAttribute('href'))).toContain('https://www.imdb.com/title/tt0040725/')
  expect(screen.getByText(/8.2\/10 · 1234 votes/)).not.toBeNull()
  expect(screen.getByRole('link', { name: 'Letterboxd' }).getAttribute('href')).toBe('https://letterboxd.com/imdb/tt0040725/')
  expect(screen.getByText(/Information courtesy of/)).not.toBeNull()
})

it('opens each person’s page from their face and name, and You from the reader’s own — AE9', async () => {
  mocks.fetchMovieNightCandidates.mockResolvedValue({ items: [{
    ...RED_SHOES,
    people: [
      { personId: CRAIG, personName: 'Craig', lastWatchedAt: '2026-10-20', personalRating: 4.5 },
      { personId: MARK, personName: 'Mark', lastWatchedAt: null, personalRating: null },
    ],
  }], total: 1 })
  renderPage()
  fireEvent.click(await screen.findByRole('button', { name: /The Red Shoes/, expanded: false }))
  const people = within(screen.getByRole('list', { name: 'Watch history and personal ratings' }))
  // Craig is reading: Mark's face and name open Mark's page; Craig's own open You.
  expect(people.getByRole('link', { name: /Mark/ }).getAttribute('href')).toBe(`/people/${MARK}`)
  expect(people.getByRole('link', { name: /Craig/ }).getAttribute('href')).toBe('/you')
})

it('says when a score and runtime are unavailable and keeps a Letterboxd search link', async () => {
  mocks.fetchMovieNightCandidates.mockResolvedValue({ items: [{ ...RED_SHOES, runtimeMinutes: null }], total: 1 })
  renderPage()
  fireEvent.click(await screen.findByRole('button', { name: /The Red Shoes/, expanded: false }))
  expect(screen.getByText('Runtime unavailable.')).not.toBeNull()
  expect(screen.getByText(/score unavailable/)).not.toBeNull()
  expect(screen.getByRole('link', { name: 'Letterboxd' }).getAttribute('href')).toBe('https://letterboxd.com/search/The%20Red%20Shoes/')
})

describe('MovieNightSessionPage — AE10 (#355)', () => {
  const WITH_MARK = {
    ...NIGHT,
    participantCount: 2,
    people: [
      { id: CRAIG, displayName: 'Craig', invited: false, added: 1, lastSeen: '2026-11-11T19:58:00Z', choosingNow: true },
      { id: MARK, displayName: 'Mark', invited: true, added: 3, lastSeen: '2026-11-11T19:59:00Z', choosingNow: true },
    ],
    invitable: [],
  }

  it('says how far Mark has got, never which films (C)', async () => {
    mocks.fetchMovieNight.mockResolvedValue(WITH_MARK)
    renderPage()

    const progress = within(await screen.findByRole('list', { name: 'How far everyone has got' }))
    expect(progress.getByText('Mark has added 3 · choosing now')).not.toBeNull()
    // Your own line is not drawn: "You've added 1" is the shortlist's.
    expect(progress.queryByText(/Craig/)).toBeNull()
  })

  it('says when Mark has not opened it, and when he is not there now (C)', async () => {
    mocks.fetchMovieNight.mockResolvedValue({
      ...WITH_MARK,
      people: [WITH_MARK.people[0], { ...WITH_MARK.people[1], added: 0, lastSeen: null, choosingNow: false }],
    })
    renderPage()
    expect(await screen.findByText('Mark hasn’t opened it yet')).not.toBeNull()
  })

  it('reads the night again when a vote arrives, which names no film (C)', async () => {
    mocks.fetchMovieNight.mockResolvedValue(WITH_MARK)
    mocks.streamMovieNightEvents.mockImplementation(async function* () {
      yield { kind: 'vote' }
    })
    renderPage()
    await waitFor(() => expect(mocks.fetchMovieNight.mock.calls.length).toBeGreaterThan(1))
    expect(mocks.fetchMovieNightCandidates).toHaveBeenCalledTimes(1)
  })

  it('says why each dealt film is on the list, under the filters it started with (B)', async () => {
    mocks.fetchMovieNight.mockResolvedValue({ ...WITH_MARK, filters: { underTwoHours: true, genre: 'Horror' } })
    const people = [
      { personId: CRAIG, personName: 'Craig', lastWatchedAt: '2020-10-31', personalRating: 5 },
      { personId: MARK, personName: 'Mark', lastWatchedAt: null, personalRating: null },
    ]
    mocks.fetchMovieNightCandidates.mockResolvedValue({
      items: [
        { ...RED_SHOES, dealtAs: 'worthARewatch', people },
        { ...RED_SHOES, suggestionId: VOTED_ID, title: 'Alien', dealtAs: 'inNeitherDiary', people: people.map((p) => ({ ...p, lastWatchedAt: null, personalRating: null })) },
      ],
      total: 2,
    })
    renderPage()

    const shelf = within(await screen.findByRole('region', { name: /From the shelf/ }))
    expect(shelf.getByText('Worth a rewatch · Craig 5/5')).not.toBeNull()
    expect(shelf.getByText('In neither diary')).not.toBeNull()
    const chips = within(shelf.getByRole('list', { name: 'Started with' }))
    expect(chips.getAllByRole('listitem').map((chip) => chip.textContent)).toEqual(['Under two hours', 'Horror'])
  })

  it('says at the match which shelf and how long, and logs it for both once (D)', async () => {
    const match = {
      movieId: MOVIE_ID, title: 'The Exorcist', year: 1973, posterPath: null, runtimeMinutes: 122,
      places: [{ location: 'Lounge', section: 'Lounge', shelf: 'Left' }], loggedAt: null,
    }
    mocks.fetchMovieNight.mockResolvedValue({ ...WITH_MARK, match })
    mocks.logMovieNight.mockResolvedValue({ ...WITH_MARK, match: { ...match, loggedAt: '2026-11-11T22:10:00Z' } })
    renderPage()

    const card = within((await screen.findByText("It's a match")).closest('[role="status"]') as HTMLElement)
    expect(card.getByText('2h 2m')).not.toBeNull()
    expect(card.getByRole('list', { name: 'Where the disc is' }).textContent).toContain('Lounge')
    fireEvent.click(card.getByRole('button', { name: 'Log it for both of us' }))

    await waitFor(() => expect(mocks.logMovieNight).toHaveBeenCalledWith(SESSION_ID))
    expect(await screen.findByText(/Logged for both of you/)).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Log it for both of us' })).toBeNull()
  })

  it('says a film nobody owns is not on the shelf, and says why logging failed (D)', async () => {
    mocks.fetchMovieNight.mockResolvedValue({
      ...WITH_MARK,
      match: { movieId: null, title: 'Rented Film', year: 1999, posterPath: null, runtimeMinutes: null, places: [], loggedAt: null },
    })
    mocks.logMovieNight.mockRejectedValue(new Error('That film is in the Trash'))
    renderPage()

    expect(await screen.findByText('Not on the shelf')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Log it for both of us' }))
    expect(await screen.findByText('That film is in the Trash')).not.toBeNull()
  })
})
