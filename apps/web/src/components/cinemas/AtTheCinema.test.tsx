// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CinemaFilms } from '@mcu/shared'

import { CINEMA_NOW, filmsFixture } from '@/pages/cinema-films-fixture'

const state = vi.hoisted(() => ({ id: 'craig', role: 'admin', online: true, fetch: vi.fn() }))
vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { id: state.id, role: state.role } }) }))
vi.mock('@/hooks/useOnlineStatus', () => ({ useOnlineStatus: () => state.online }))
vi.mock('@/lib/api', () => ({ fetchCinemaFilms: state.fetch, posterUrl: (path: string | null) => path ?? '/placeholder-poster.svg' }))
import { AtTheCinema } from './AtTheCinema'

function Where() {
  const { pathname, search } = useLocation()
  return <output aria-label="Address">{pathname + search}</output>
}

function setup(path = '/movie-night/cinema') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const tree = () => <QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><AtTheCinema /><Where /></MemoryRouter></QueryClientProvider>
  return { ...render(tree()), tree }
}

const grid = (name: string) => screen.getByRole('region', { name })
const titles = (region: HTMLElement) => within(region).getAllByRole('article').map((card) => card.getAttribute('aria-label'))

beforeEach(() => {
  state.id = 'craig'; state.role = 'admin'; state.online = true
  vi.spyOn(Date, 'now').mockReturnValue(CINEMA_NOW)
  state.fetch.mockReset().mockResolvedValue(filmsFixture())
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('At the cinema, film first (AC4)', () => {
  it('puts this week’s films first, widest first, then what opens later, then listings and events', async () => {
    // AE5: every day at once is "All days", the strip's last choice.
    setup('/movie-night/cinema?day=all')
    await screen.findByRole('region', { name: 'This week' })
    expect(titles(grid('This week'))).toEqual(['A returning favourite', 'A current first run'])
    expect(titles(grid('Coming up'))).toEqual(['Opening later'])
    expect(titles(grid('Not matched to a film yet'))).toEqual(['An uncertain programme', 'Waiting film'])
    expect(titles(grid('Events and double bills'))).toEqual(['NT Live: Hamlet'])
    // Each film: its poster, its run, how many cinemas and its next showing.
    const favourite = within(grid('This week')).getByRole('article', { name: 'A returning favourite' })
    expect(within(favourite).getByText('Rerun')).toBeTruthy()
    expect(within(favourite).getByText('2 cinemas')).toBeTruthy()
    expect(within(favourite).getByText('Today 20:00')).toBeTruthy()
    expect(within(favourite).getByText('Seen')).toBeTruthy()
    expect(within(favourite).getByRole('link').getAttribute('href')).toBe('/movie-night/cinema/tmdb-1417')
    const fresh = within(grid('This week')).getByRole('article', { name: 'A current first run' })
    expect(within(fresh).getByText('First run')).toBeTruthy()
    expect(within(fresh).getByText('ODEON Kilmarnock')).toBeTruthy()
    expect(within(fresh).getByText('Thu 5 19:30')).toBeTruthy()
    // A listing says what it is where a film says its run.
    expect(within(grid('Not matched to a film yet')).getByText(/Not matched yet · Vue St Enoch/)).toBeTruthy()
    // AE5 (#355, point 13): both kept closed until opened, the count in the heading.
    for (const [name, count] of [['Not matched to a film yet', 2], ['Events and double bills', 1]] as const) {
      expect(grid(name).querySelector('details')?.open).toBe(false)
      expect(within(grid(name)).getByRole('heading').textContent).toBe(`${name} · ${String(count)}`)
    }
  })

  it('says which cinemas list only to a date, and that coverage is partial', async () => {
    setup()
    const horizons = await screen.findByRole('region', { name: 'How far ahead cinemas list' })
    expect(within(horizons).getByText('Vue St Enoch: listed only to Wed 4 Nov')).toBeTruthy()
    expect(within(horizons).getByText('ODEON Kilmarnock: listed only to Mon 9 Nov')).toBeTruthy()
    expect(screen.getByText(/Partial coverage:/)).toBeTruthy()
  })

  it('filters by run with counts taken before the run, and keeps the choice in the address', async () => {
    setup('/movie-night/cinema?day=all')
    await screen.findByRole('region', { name: 'This week' })
    const runs = within(screen.getByRole('group', { name: 'Run' }))
    expect(runs.getAllByRole('button').map((button) => button.textContent)).toEqual(['All films6', 'New releases2', 'Older films1', 'Unclassified3'])
    fireEvent.click(runs.getByRole('button', { name: /^Older films/ }))
    expect(titles(grid('This week'))).toEqual(['A returning favourite'])
    expect(screen.queryByRole('region', { name: 'Coming up' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Not matched to a film yet' })).toBeNull()
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?day=all&run=olderFilm')
    fireEvent.click(runs.getByRole('button', { name: /^Unclassified/ }))
    expect(titles(grid('Not matched to a film yet'))).toEqual(['An uncertain programme', 'Waiting film'])
    expect(screen.queryByRole('region', { name: 'This week' })).toBeNull()
  })

  it('narrows to one day, and to the cinemas chosen, without another request', async () => {
    setup('/movie-night/cinema?day=2026-11-05')
    const day = await screen.findByRole('region', { name: 'Thu 5 Nov' })
    expect(titles(day)).toEqual(['A current first run'])
    fireEvent.click(within(screen.getByRole('group', { name: 'Day' })).getByRole('button', { name: 'All days' }))
    // AE4: the chip counts the cinemas rather than saying nine; this fixture has two.
    fireEvent.click(screen.getByText('Cinemas · all 2'))
    fireEvent.click(screen.getByRole('checkbox', { name: 'Vue Glasgow St Enoch' }))
    const favourite = within(grid('This week')).getByRole('article', { name: 'A returning favourite' })
    expect(within(favourite).getByText('ODEON Kilmarnock')).toBeTruthy()
    expect(screen.queryByRole('article', { name: 'An uncertain programme' })).toBeNull()
    // AF3 (#372): every day at once is the default, so it needs no word in the address.
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?cinema=odeon-kilmarnock')
    fireEvent.click(screen.getByRole('checkbox', { name: 'ODEON Kilmarnock' }))
    expect(screen.getByText('Select at least one cinema.')).toBeTruthy()
    expect(screen.queryAllByRole('article')).toHaveLength(0)
    expect(state.fetch).toHaveBeenCalledTimes(1)
  })

  it('links Craig to the check a listing waits for, and shows Mark the state alone (AC3)', async () => {
    setup('/movie-night/cinema?day=all')
    const waiting = await screen.findByRole('article', { name: 'Waiting film' })
    expect(within(waiting).getByText(/Waiting for a check/)).toBeTruthy()
    expect(within(waiting).getByRole('link', { name: 'Check which film this is' }).getAttribute('href')).toBe('/identify')
    cleanup()
    state.id = 'mark'; state.role = 'viewer'
    setup('/movie-night/cinema?day=all')
    const marks = await screen.findByRole('article', { name: 'Waiting film' })
    expect(within(marks).getByText(/Waiting for a check/)).toBeTruthy()
    expect(within(marks).queryByRole('link', { name: 'Check which film this is' })).toBeNull()
  })

  it('drops a showing as it starts, on focus, without asking again', async () => {
    setup()
    await screen.findByRole('article', { name: 'A returning favourite' })
    vi.mocked(Date.now).mockReturnValue(Date.parse('2026-11-03T21:30:00Z'))
    fireEvent.focus(window)
    await waitFor(() => expect(screen.queryByRole('article', { name: 'A returning favourite' })).toBeNull())
    expect(state.fetch).toHaveBeenCalledTimes(1)
  })

  it('never draws another person’s watch marks while their own read is coming', async () => {
    const mounted = setup()
    await screen.findByText('Seen')
    state.fetch.mockImplementationOnce(() => new Promise<CinemaFilms>(() => undefined))
    state.id = 'mark'
    mounted.rerender(mounted.tree())
    await waitFor(() => expect(screen.queryByText('Seen')).toBeNull())
    expect(state.fetch).toHaveBeenCalledTimes(2)
  })

  it('keeps every official programme when the first read fails, and says when offline', async () => {
    state.fetch.mockRejectedValueOnce(new Error('Unavailable'))
    setup()
    const fallback = await screen.findByRole('region', { name: 'Official cinema programmes' })
    // AE4 (#355): ten since the Omniplex joined the nine.
    expect(within(fallback).getAllByRole('link')).toHaveLength(10)
    cleanup()
    state.online = false
    setup()
    expect(await screen.findByText(/Offline · saved programme only/)).toBeTruthy()
  })

  it('says so when nothing is listed for a choice', async () => {
    const empty = filmsFixture(); empty.films = []
    state.fetch.mockResolvedValue(empty)
    setup('/movie-night/cinema?day=all&run=olderFilm')
    expect(await screen.findByText('No older films listed')).toBeTruthy()
    fireEvent.click(screen.getByText('Coverage and sources'))
    expect(screen.getByText('Source: CinemaTimes')).toBeTruthy()
  })
})

it('opens New this week directly, preserves the run filter and distinguishes old answers', async () => {
  const data = filmsFixture()
  const card = data.films.find((film) => film.key === 'tmdb-1417')!
  data.newThisWeek = [{ key: card.key, title: card.title, card, firstListedAtUtc: '2026-11-02T08:00:00Z', recognisedAtUtc: '2026-11-03T08:00:00Z', isReturn: true, runLabels: ['Rerun'], runReasons: ['UK release 1990 · rerun'] }]
  state.fetch.mockResolvedValue(data)
  setup('/movie-night/cinema?view=new-this-week&run=olderFilm')
  const section = await screen.findByRole('region', { name: 'New this week' })
  expect(within(section).getByRole('article', { name: card.title })).toBeTruthy()
  expect(within(section).getByText('Back in the programme')).toBeTruthy()
  expect(screen.queryByRole('region', { name: 'This week' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'All films' }))
  expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?run=olderFilm')
})

it('does not turn a missing New this week field into an empty programme claim', async () => {
  setup('/movie-night/cinema?view=new-this-week')
  expect(await screen.findByText('New this week is not available in this saved programme. Reload when connected.')).toBeTruthy()
  expect(screen.queryByText('No new films at your cinemas this week.')).toBeNull()
})

// AE5 (#355, points 4, 8 and 13): the day-by-day view, as the cinema apps have it.
describe('At the cinema, day by day (AE5)', () => {
  const dayGroup = () => within(screen.getByRole('group', { name: 'Day' }))

  it('opens All films, All days with nothing in the address (AF3, #372), the strip first, All days leading', async () => {
    setup()
    expect(await screen.findByRole('region', { name: 'This week' })).toBeTruthy()
    expect(dayGroup().getAllByRole('button')[0].textContent).toBe('All days')
    expect(dayGroup().getByRole('button', { name: 'All days' }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('group', { name: 'Programme view' }).querySelector('[aria-pressed="true"]')?.textContent).toBe('All films')
    expect(screen.queryByRole('region', { name: 'Tue 3 Nov' })).toBeNull()
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema')
  })

  it('opens a picked day, each film’s times by cinema, each time booking, its films opening on that day', async () => {
    setup('/movie-night/cinema?day=2026-11-03')
    const today = await screen.findByRole('region', { name: 'Tue 3 Nov' })
    expect(dayGroup().getByRole('button', { name: 'Tue 3 Nov' }).getAttribute('aria-pressed')).toBe('true')
    // The strip leads: it comes before the run filter.
    const strip = screen.getByRole('group', { name: 'Day' }), run = screen.getByRole('group', { name: 'Run' })
    expect(strip.compareDocumentPosition(run) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    const favourite = within(today).getByRole('article', { name: 'A returning favourite' })
    const vue = within(favourite).getByRole('list', { name: 'Times at Vue Glasgow St Enoch' })
    expect(within(vue).getByRole('link', { name: 'Book 20:00 at Vue Glasgow St Enoch' }).getAttribute('href')).toBe('https://www.myvue.com/book-tickets/summary/10097/1')
    const odeon = within(favourite).getByRole('list', { name: 'Times at ODEON Kilmarnock' })
    expect(within(odeon).getByRole('link', { name: 'Book 21:00 IMAX at ODEON Kilmarnock' })).toBeTruthy()
    // Listings keep their own folded rows; the day has no film grid of next times.
    expect(screen.queryByRole('region', { name: 'This week' })).toBeNull()
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?day=2026-11-03')
    // AF3: the film's page opens on the day picked here.
    expect(within(favourite).getByRole('link', { name: 'A returning favourite' }).getAttribute('href')).toBe('/movie-night/cinema/tmdb-1417?day=2026-11-03')
  })

  it('hides times already past today, and offers tomorrow when none are left', async () => {
    vi.mocked(Date.now).mockReturnValue(Date.parse('2026-11-03T20:30:00Z'))
    setup('/movie-night/cinema?day=2026-11-03')
    const favourite = await screen.findByRole('article', { name: 'A returning favourite' })
    expect(within(favourite).queryByRole('list', { name: 'Times at Vue Glasgow St Enoch' })).toBeNull()
    expect(within(favourite).getByRole('list', { name: 'Times at ODEON Kilmarnock' })).toBeTruthy()
    cleanup()
    vi.mocked(Date.now).mockReturnValue(Date.parse('2026-11-03T22:30:00Z'))
    setup('/movie-night/cinema?day=2026-11-03')
    expect(await screen.findByText('Nothing more today')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'See tomorrow' }))
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?day=2026-11-04')
  })

  it('greys a day with nothing showing, and keeps the day in the address', async () => {
    setup()
    await screen.findByRole('region', { name: 'This week' })
    expect(dayGroup().getByRole('button', { name: 'Sat 7 Nov' }).getAttribute('title')).toBe('Nothing showing')
    expect(dayGroup().getByRole('button', { name: 'Thu 5 Nov' }).getAttribute('title')).toBeNull()
    fireEvent.click(dayGroup().getByRole('button', { name: 'Thu 5 Nov' }))
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?day=2026-11-05')
    expect(within(screen.getByRole('region', { name: 'Thu 5 Nov' })).getByRole('article', { name: 'A current first run' })).toBeTruthy()
    // Today is named too, since every day at once is the default (AF3).
    fireEvent.click(dayGroup().getByRole('button', { name: 'Tue 3 Nov' }))
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?day=2026-11-03')
    fireEvent.click(dayGroup().getByRole('button', { name: 'All days' }))
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema')
  })

  it('books nothing offline: the times stay, as plain chips', async () => {
    state.online = false
    setup('/movie-night/cinema?day=2026-11-03')
    const favourite = await screen.findByRole('article', { name: 'A returning favourite' })
    expect(within(favourite).queryAllByRole('link', { name: /^Book / })).toHaveLength(0)
    expect(within(within(favourite).getByRole('list', { name: 'Times at ODEON Kilmarnock' })).getByText('21:00')).toBeTruthy()
  })

  it('reads a day already gone in the address, and AE5’s "all", as every day (AF3)', async () => {
    setup('/movie-night/cinema?day=2026-11-01')
    expect(await screen.findByRole('region', { name: 'This week' })).toBeTruthy()
    expect(dayGroup().getByRole('button', { name: 'All days' }).getAttribute('aria-pressed')).toBe('true')
    cleanup()
    setup('/movie-night/cinema?day=all')
    expect(await screen.findByRole('region', { name: 'This week' })).toBeTruthy()
    expect(dayGroup().getByRole('button', { name: 'All days' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('says when today’s films are over, even with a listing still to start', async () => {
    // 21:30: both of the favourite's times are gone; the uncertain listing at 22:00 is not.
    vi.mocked(Date.now).mockReturnValue(Date.parse('2026-11-03T21:30:00Z'))
    setup('/movie-night/cinema?day=2026-11-03')
    expect(await screen.findByText('Nothing more today')).toBeTruthy()
    expect(screen.getByText('Every film listed for today has started. Listings not matched yet and events are below.')).toBeTruthy()
    expect(within(grid('Not matched to a film yet')).getByRole('heading').textContent).toBe('Not matched to a film yet · 1')
    expect(screen.getByRole('button', { name: 'See tomorrow' })).toBeTruthy()
  })

  it('runs the strip to the furthest listing, and a day past one cinema’s list shows the others', async () => {
    setup()
    await screen.findByRole('region', { name: 'This week' })
    const days = dayGroup().getAllByRole('button')
    // All days first (AF3), then today to the last showing (12 Nov); Vue lists only to 4 Nov.
    expect(days.map((day) => day.textContent)).toEqual(['All days', 'Today', 'Tomorrow', 'Thu 5', 'Fri 6', 'Sat 7', 'Sun 8', 'Mon 9', 'Tue 10', 'Wed 11', 'Thu 12'])
    fireEvent.click(dayGroup().getByRole('button', { name: 'Thu 5 Nov' }))
    const thursday = screen.getByRole('region', { name: 'Thu 5 Nov' })
    expect(within(thursday).queryByRole('list', { name: 'Times at Vue Glasgow St Enoch' })).toBeNull()
    expect(within(thursday).getByRole('list', { name: 'Times at ODEON Kilmarnock' })).toBeTruthy()
    expect(within(screen.getByRole('region', { name: 'How far ahead cinemas list' })).getByText('Vue St Enoch: listed only to Wed 4 Nov')).toBeTruthy()
  })

  it('lists ten cinemas’ times under one film, each cinema once, and All / None over the ten', async () => {
    const data = filmsFixture()
    const [vue] = data.venues
    const more = Array.from({ length: 8 }, (_, n) => ({ ...vue, id: `00000000-0000-4000-8000-${String(700 + n).padStart(12, '0')}`, slug: `cinema-${String(n + 3)}`, name: `Cinema ${String(n + 3)}` }))
    data.venues.push(...more)
    const favourite = data.films[0]
    favourite.slots.push(...more.map((venue, n) => ({ ...favourite.slots[0], venueId: venue.id, startsAtUtc: [`2026-11-03T${String(18 + (n % 4))}:15:00Z`], times: [{ at: `2026-11-03T${String(18 + (n % 4))}:15:00Z`, bookingUrl: null, formats: [] }] })))
    state.fetch.mockResolvedValue(data)
    setup('/movie-night/cinema?day=2026-11-03')
    const card = await screen.findByRole('article', { name: 'A returning favourite' })
    expect(within(card).getAllByRole('list', { name: /^Times at / })).toHaveLength(10)
    fireEvent.click(screen.getByText('Cinemas · all 10'))
    expect(screen.getAllByRole('checkbox')).toHaveLength(10)
    fireEvent.click(screen.getByRole('checkbox', { name: 'Cinema 3' }))
    expect(screen.getByText('Cinemas · 9 of 10')).toBeTruthy()
    expect(within(card).getAllByRole('list', { name: /^Times at / })).toHaveLength(9)
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    expect(screen.getByText('Cinemas · all 10')).toBeTruthy()
  })

  it('ticks every cinema or none at once', async () => {
    setup()
    await screen.findByRole('region', { name: 'This week' })
    fireEvent.click(screen.getByText('Cinemas · all 2'))
    fireEvent.click(screen.getByRole('button', { name: 'None' }))
    expect(screen.getByText('Select at least one cinema.')).toBeTruthy()
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema?cinema=none')
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    expect(screen.queryByText('Select at least one cinema.')).toBeNull()
    expect(screen.getByLabelText('Address').textContent).toBe('/movie-night/cinema')
  })
})

