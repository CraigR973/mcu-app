// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { detailFixture } from './cinema-films-fixture'
import { ALEX, CINEMA_NOW, MARK, TRIP, tripFixture } from './cinema-trip-fixture'

const state = vi.hoisted(() => ({ online: true }))
const api = vi.hoisted(() => ({
  fetchCinemaTrip: vi.fn(),
  fetchCinemaFilm: vi.fn(),
  fetchInvitablePeople: vi.fn(),
  replyToCinemaTrip: vi.fn(),
  moveCinemaTrip: vi.fn(),
  keepCinemaTripTime: vi.fn(),
  inviteToCinemaTrip: vi.fn(),
  cancelCinemaTrip: vi.fn(),
}))
vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { id: 'reader', role: 'viewer' } }) }))
vi.mock('@/hooks/useOnlineStatus', () => ({ useOnlineStatus: () => state.online }))
vi.mock('@/lib/api', async (importOriginal) => ({ ...(await importOriginal<typeof import('@/lib/api')>()), ...api }))

import { ApiError } from '@/lib/api'
import CinemaTripPage from './CinemaTripPage'

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/movie-night/trips/${TRIP}`]}>
        <Routes><Route path="/movie-night/trips/:id" element={<CinemaTripPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  state.online = true
  vi.spyOn(Date, 'now').mockReturnValue(CINEMA_NOW)
  for (const fn of Object.values(api)) fn.mockReset()
  api.fetchCinemaFilm.mockResolvedValue(detailFixture())
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('a cinema trip, as an invitee reads it (AC5)', () => {
  it('shows the film, the showing, Check tickets and everyone’s reply, the organiser first', async () => {
    api.fetchCinemaTrip.mockResolvedValue(tripFixture())
    setup()
    expect(await screen.findByRole('heading', { level: 1, name: 'A returning favourite' })).toBeTruthy()
    expect(screen.getByText('Tue 3 Nov · 21:00 · ODEON Kilmarnock')).toBeTruthy()
    const tickets = screen.getByRole('link', { name: /Check tickets at ODEON Kilmarnock/ })
    expect(tickets.getAttribute('href')).toContain('odeon.co.uk/ticketing')
    expect(screen.getByRole('link', { name: 'Every showing of this film' }).getAttribute('href')).toBe('/movie-night/cinema/tmdb-1417')
    const going = within(screen.getByRole('region', { name: 'Who’s going' }))
    expect(going.getByText('1 going · 2 no reply yet')).toBeTruthy()
    const rows = going.getAllByRole('listitem').map((row) => row.textContent)
    expect(rows).toEqual(['CraigOrganising', 'AlexNo reply yet', 'Mark (you)No reply yet'])
    // An invitee has no organiser's controls.
    expect(screen.queryByRole('region', { name: 'Change the trip' })).toBeNull()
  })

  it('replies against the trip’s revision, and the answer redraws the page', async () => {
    api.fetchCinemaTrip.mockResolvedValue(tripFixture({ revision: 3 }))
    api.replyToCinemaTrip.mockResolvedValue(tripFixture({ revision: 3, yourReply: 'going', counts: { going: 2, notGoing: 0, anotherTime: 0, invited: 1 } }))
    setup()
    const reply = within(await screen.findByRole('region', { name: 'Your reply' }))
    fireEvent.click(reply.getByRole('button', { name: 'Going' }))
    await waitFor(() => expect(api.replyToCinemaTrip).toHaveBeenCalledWith(TRIP, { revision: 3, reply: 'going' }))
    expect(await screen.findByText('2 going · 1 no reply yet')).toBeTruthy()
  })

  it('suggests another of the film’s confirmed times, never the trip’s own', async () => {
    api.fetchCinemaTrip.mockResolvedValue(tripFixture())
    api.replyToCinemaTrip.mockResolvedValue(tripFixture())
    setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Another time' }))
    const own = detailFixture().showings[1]
    const pick = await screen.findByRole('button', { name: /^20:00 IMAX at Vue Glasgow St Enoch/ })
    expect(screen.queryByRole('button', { name: /^21:00 at ODEON Kilmarnock/ })).toBeNull()
    expect(screen.getByRole('button', { name: 'Suggest this time' }).hasAttribute('disabled')).toBe(true)
    fireEvent.click(pick)
    fireEvent.click(screen.getByRole('button', { name: 'Suggest this time' }))
    await waitFor(() => expect(api.replyToCinemaTrip).toHaveBeenCalledWith(TRIP, {
      revision: 1, reply: 'anotherTime', showingId: detailFixture().showings[0]?.id,
    }))
    expect(own).toBeTruthy()
  })

  it('says a refusal in the API’s words, and reads the trip again', async () => {
    api.fetchCinemaTrip.mockResolvedValue(tripFixture())
    api.replyToCinemaTrip.mockRejectedValue(new ApiError('The trip has moved. Check the new time and reply again.', 409))
    setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Not going' }))
    expect((await screen.findByRole('alert')).textContent).toBe('The trip has moved. Check the new time and reply again.')
    await waitFor(() => expect(api.fetchCinemaTrip).toHaveBeenCalledTimes(2))
  })

  it('writes nothing offline, and says when it can', async () => {
    state.online = false
    api.fetchCinemaTrip.mockResolvedValue(tripFixture())
    setup()
    const reply = within(await screen.findByRole('region', { name: 'Your reply' }))
    expect(reply.getByRole('button', { name: 'Going' }).hasAttribute('disabled')).toBe(true)
    expect(screen.getByText('You’re offline. Reply when you have signal.')).toBeTruthy()
    // Ticket links pause offline, as on the film page.
    expect(screen.queryByRole('link', { name: /Check tickets/ })).toBeNull()
  })

  it('says a withdrawn time without asking an invitee to act, and drops Check tickets', async () => {
    const trip = tripFixture()
    api.fetchCinemaTrip.mockResolvedValue({ ...trip, showing: { ...trip.showing, flag: 'withdrawn', live: null, venue: null } })
    setup()
    expect(await screen.findByText('ODEON Kilmarnock no longer lists this time.')).toBeTruthy()
    expect(screen.queryByText(/Pick another time or cancel/)).toBeNull()
    expect(screen.queryByRole('link', { name: /Check tickets/ })).toBeNull()
  })

  it('reads a cancelled trip as frozen, with no reply buttons', async () => {
    api.fetchCinemaTrip.mockResolvedValue(tripFixture({ status: 'cancelled', cancelledAtUtc: '2026-11-03T15:00:00Z' }))
    setup()
    expect(await screen.findByText('Craig cancelled this trip.')).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Your reply' })).toBeNull()
  })

  it('answers someone not on the trip as no trip at all', async () => {
    api.fetchCinemaTrip.mockRejectedValue(new ApiError('Trip not found', 404))
    setup()
    expect(await screen.findByText('Trip not found')).toBeTruthy()
  })
})

describe('a cinema trip, as its organiser reads it (AC5)', () => {
  const suggesting = () => {
    const trip = tripFixture({ asCraig: true })
    return tripFixture({
      asCraig: true,
      counts: { going: 1, notGoing: 0, anotherTime: 1, invited: 1 },
      invitees: trip.invitees.map((person) => person.profileId === MARK ? {
        ...person, reply: 'anotherTime' as const, replyRevision: 2, repliedAtUtc: '2026-11-03T13:00:00Z',
        suggestion: { showingId: detailFixture().showings[2]?.id ?? null, venueName: 'ODEON Kilmarnock', startsAtUtc: '2026-11-04T18:30:00Z', formats: [], flag: null },
      } : person),
    })
  }

  it('accepts a suggestion, naming whose and the reply it was shown at', async () => {
    api.fetchCinemaTrip.mockResolvedValue(suggesting())
    api.moveCinemaTrip.mockResolvedValue(tripFixture({ asCraig: true, revision: 2 }))
    setup()
    expect(await screen.findByText('Suggests Wed 4 Nov 18:30 · ODEON Kilmarnock')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Accept this time' }))
    await waitFor(() => expect(api.moveCinemaTrip).toHaveBeenCalledWith(TRIP, {
      revision: 1, showingId: detailFixture().showings[2]?.id, fromProfileId: MARK, fromReplyRevision: 2,
    }))
  })

  it('keeps the trip’s time, telling the suggester', async () => {
    api.fetchCinemaTrip.mockResolvedValue(suggesting())
    api.keepCinemaTripTime.mockResolvedValue(tripFixture({ asCraig: true }))
    setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Keep this time' }))
    await waitFor(() => expect(api.keepCinemaTripTime).toHaveBeenCalledWith(TRIP, { profileId: MARK, replyRevision: 2 }))
  })

  it('cannot accept a suggestion the cinema no longer lists', async () => {
    const trip = suggesting()
    trip.invitees = trip.invitees.map((person) => person.suggestion ? { ...person, suggestion: { ...person.suggestion, flag: 'withdrawn' as const } } : person)
    api.fetchCinemaTrip.mockResolvedValue(trip)
    setup()
    expect(await screen.findByText(/no longer listed/)).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Accept this time' }).hasAttribute('disabled')).toBe(true)
  })

  it('is asked to pick another time or cancel when the cinema withdraws the time', async () => {
    const trip = tripFixture({ asCraig: true })
    api.fetchCinemaTrip.mockResolvedValue({ ...trip, showing: { ...trip.showing, flag: 'cancelled', live: null, venue: null } })
    setup()
    expect(await screen.findByText('ODEON Kilmarnock has cancelled this showing. Pick another time or cancel.')).toBeTruthy()
  })

  it('moves the trip to a time of their own', async () => {
    api.fetchCinemaTrip.mockResolvedValue(tripFixture({ asCraig: true }))
    api.moveCinemaTrip.mockResolvedValue(tripFixture({ asCraig: true, revision: 2 }))
    setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Move to another time' }))
    fireEvent.click(await screen.findByRole('button', { name: /^18:30 at ODEON Kilmarnock/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Move the trip' }))
    await waitFor(() => expect(api.moveCinemaTrip).toHaveBeenCalledWith(TRIP, { revision: 1, showingId: detailFixture().showings[2]?.id }))
  })

  it('invites more people, offering only those not on the trip', async () => {
    api.fetchCinemaTrip.mockResolvedValue(tripFixture({ asCraig: true }))
    api.fetchInvitablePeople.mockResolvedValue({ people: [
      { profileId: ALEX, displayName: 'Alex', isYou: false },
      { profileId: MARK, displayName: 'Mark', isYou: false },
      { profileId: '00000000-0000-4000-8000-000000000799', displayName: 'Sam', isYou: false },
    ] })
    api.inviteToCinemaTrip.mockResolvedValue(tripFixture({ asCraig: true }))
    setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Invite more' }))
    const sam = await screen.findByRole('checkbox', { name: 'Sam' })
    expect(screen.queryByRole('checkbox', { name: 'Mark' })).toBeNull()
    expect((sam as HTMLInputElement).checked).toBe(false)
    fireEvent.click(sam)
    fireEvent.click(screen.getByRole('button', { name: 'Send invitations' }))
    await waitFor(() => expect(api.inviteToCinemaTrip).toHaveBeenCalledWith(TRIP, ['00000000-0000-4000-8000-000000000799']))
  })

  it('cancels only after saying so', async () => {
    api.fetchCinemaTrip.mockResolvedValue(tripFixture({ asCraig: true }))
    api.cancelCinemaTrip.mockResolvedValue(tripFixture({ asCraig: true, status: 'cancelled', cancelledAtUtc: '2026-11-03T17:00:00Z' }))
    setup()
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel trip' }))
    expect(api.cancelCinemaTrip).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel the trip' }))
    await waitFor(() => expect(api.cancelCinemaTrip).toHaveBeenCalledWith(TRIP))
    expect(await screen.findByText('You cancelled this trip.')).toBeTruthy()
  })
})
