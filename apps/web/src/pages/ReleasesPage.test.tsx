// @vitest-environment happy-dom
import { onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CalendarEntry, CalendarMonth, ReleaseType } from '@mcu/shared'

import { CINEMA_NOW, filmsFixture } from './cinema-films-fixture'

const state = vi.hoisted(() => ({
  role: 'admin',
  month: vi.fn(),
  calendar: vi.fn(),
  films: vi.fn(),
  newReleases: vi.fn(),
  ingest: vi.fn(),
  subscribe: vi.fn(),
}))
vi.mock('@/context/auth', () => ({ useAuth: () => ({ profile: { id: 'craig', role: state.role } }) }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchCalendarMonth: state.month,
  fetchCalendar: state.calendar,
  fetchCinemaFilms: state.films,
  fetchNewReleases: state.newReleases,
  ingestCalendar: state.ingest,
  subscribeToCalendar: state.subscribe,
}))
import ReleasesPage from './ReleasesPage'

const uid = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const LABELS: Record<ReleaseType, string> = {
  '4k_uhd_release': '4K UHD', blu_ray_release: 'Blu-ray', streaming_release: 'Streaming', theatrical: 'In cinemas', award_ceremony: 'Awards', sale_event: 'Sale',
}

function entry(n: number, title: string, releaseType: ReleaseType, releaseDate: string, changes: Partial<CalendarEntry> = {}): CalendarEntry {
  return {
    id: uid(n), title, releaseType, typeLabel: LABELS[releaseType], releaseDate, label: null, region: 'GB', url: null,
    posterPath: null, overview: null, movieId: null, tmdbId: releaseType === 'sale_event' ? null : 9000 + n, ...changes,
  }
}

/** November 2026 as the live calendar holds it, every type in one list: what an API from before
 *  AC7, or a month cached before it, answers whatever was asked. */
const NOVEMBER = [
  entry(1, 'A 4K restoration', '4k_uhd_release', '2026-11-09'),
  entry(2, 'A Blu-ray edition', 'blu_ray_release', '2026-11-16'),
  entry(3, 'Criterion Winter Sale (expected)', 'sale_event', '2026-11-11'),
  entry(4, 'A current first run', 'theatrical', '2026-11-05', { tmdbId: 2001 }),
  entry(5, 'A returning favourite', 'theatrical', '2026-11-06', { tmdbId: 1417 }),
  // The title of a listing the cinemas have not matched to a film yet: never linked on that.
  entry(6, 'An uncertain programme', 'theatrical', '2026-11-06', { tmdbId: 3001 }),
  entry(7, 'Nowhere near here', 'theatrical', '2026-11-13', { tmdbId: 3002 }),
  entry(8, 'Already on the shelves', 'theatrical', '2026-11-20', { tmdbId: 3003, movieId: uid(80) }),
]

function monthOf(month: string, entries: CalendarEntry[]): CalendarMonth {
  const days: CalendarMonth['days'] = {}
  for (const item of entries.filter((e) => e.releaseDate.startsWith(month))) days[item.releaseDate] = [...(days[item.releaseDate] ?? []), item]
  return { month, days, total: entries.length, types: ['4k_uhd_release', 'blu_ray_release', 'streaming_release', 'theatrical', 'award_ceremony', 'sale_event'] }
}

function Where() {
  const location = useLocation()
  return <output aria-label="Address">{`${location.pathname}${location.search}`}</output>
}

function setup(address: string, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[address]}>
        <Routes>
          <Route path="/calendar" element={<ReleasesPage />} />
          <Route path="/calendar/cinema" element={<ReleasesPage view="cinema" />} />
        </Routes>
        <Where />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return client
}

const address = () => screen.getByRole('status', { name: 'Address' }).textContent
const month = () => screen.getByRole('region', { name: /releases by month/ })

beforeEach(() => {
  state.role = 'admin'
  vi.spyOn(Date, 'now').mockReturnValue(CINEMA_NOW)
  state.month.mockReset().mockImplementation((key: string) => Promise.resolve(monthOf(key, NOVEMBER)))
  state.calendar.mockReset().mockResolvedValue({ items: NOVEMBER, total: NOVEMBER.length, refreshedAt: null })
  state.films.mockReset().mockResolvedValue(filmsFixture())
  state.newReleases.mockReset().mockResolvedValue({ items: [], basedOnGenres: [] })
  state.ingest.mockReset().mockResolvedValue({ created: 2, updated: 1, unchanged: 3, skipped: 0, total: 6, errors: [], dryRun: false })
  state.subscribe.mockReset().mockResolvedValue({
    path: '/api/v1/calendar.ics?token=abc', discPath: '/api/v1/calendar.ics?token=abc&calendar=disc',
    cinemaPath: '/api/v1/calendar.ics?token=abc&calendar=cinema', createdAt: '2026-11-03T17:00:00Z', replacedPrevious: false,
  })
})
afterEach(() => { cleanup(); onlineManager.setOnline(true); vi.restoreAllMocks() })

describe('Releases as two calendars (AC7)', () => {
  it('opens on Disc releases: the month’s 4K, Blu-ray and sale dates, and never a cinema date', async () => {
    setup('/calendar?month=2026-11')
    const views = screen.getByRole('navigation', { name: 'Release calendars' })
    expect(within(views).getByRole('link', { name: 'Disc releases' }).getAttribute('aria-current')).toBe('page')
    expect(await within(month()).findByText('A 4K restoration')).toBeTruthy()
    expect(within(month()).getByText('A Blu-ray edition')).toBeTruthy()
    expect(within(month()).getByText('Criterion Winter Sale (expected)')).toBeTruthy()
    expect(within(month()).queryByText('A current first run')).toBeNull()
    expect(state.month).toHaveBeenCalledWith('2026-11', ['4k_uhd_release', 'blu_ray_release', 'sale_event'])
    // Coming to disc stays above the month, disc-only, as it was.
    const coming = await screen.findByRole('region', { name: /Coming to disc/ })
    expect(within(coming).queryByText('A current first run')).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Coming soon' })).toBeNull()
  })

  it('makes sale events a filter, and each disc format too, kept in the address', async () => {
    setup('/calendar?month=2026-11')
    const show = await screen.findByRole('group', { name: 'Show' })
    expect(within(show).getAllByRole('button').map((chip) => chip.textContent)).toEqual(['All3', '4K UHD1', 'Blu-ray1', 'Sale events1'])
    fireEvent.click(within(show).getByRole('button', { name: /Sale events/ }))
    await waitFor(() => expect(within(month()).queryByText('A 4K restoration')).toBeNull())
    expect(within(month()).getByText('Criterion Winter Sale (expected)')).toBeTruthy()
    expect(address()).toBe('/calendar?month=2026-11&show=sales')
    fireEvent.click(within(show).getByRole('button', { name: /4K UHD/ }))
    await waitFor(() => expect(within(month()).queryByText('Criterion Winter Sale (expected)')).toBeNull())
    expect(within(month()).getByText('A 4K restoration')).toBeTruthy()
    fireEvent.click(within(show).getByRole('button', { name: /^All/ }))
    expect(address()).toBe('/calendar?month=2026-11')
  })

  it('lists UK cinema dates on Cinema releases, a film showing at the nine opening its page', async () => {
    setup('/calendar/cinema?month=2026-11')
    const views = screen.getByRole('navigation', { name: 'Release calendars' })
    expect(within(views).getByRole('link', { name: 'Cinema releases' }).getAttribute('aria-current')).toBe('page')
    const first = await within(month()).findByRole('link', { name: /A current first run/ })
    expect(first.getAttribute('href')).toBe('/movie-night/cinema/tmdb-2001')
    expect(first.textContent).toContain('At one of your cinemas')
    expect(within(month()).getByRole('link', { name: /A returning favourite/ }).textContent).toContain('At 2 of your cinemas')
    expect(state.month).toHaveBeenCalledWith('2026-11', ['theatrical'])
    // The same title as a listing not matched yet is not a link; neither is a film not showing.
    expect(within(month()).getByText('An uncertain programme').closest('a')).toBeNull()
    expect(within(month()).getByText('Nowhere near here').closest('a')).toBeNull()
    expect(within(month()).getByRole('link', { name: /Already on the shelves/ }).getAttribute('href')).toBe(`/movies/${uid(80)}`)
    expect(within(month()).queryByText('A 4K restoration')).toBeNull()
    expect(within(month()).queryByText('Criterion Winter Sale (expected)')).toBeNull()
    expect(screen.getByText(/2 cinema listings are not matched to a film yet; a release among them links once it is\. Matching runs each morning\./)).toBeTruthy()
    expect(screen.queryByRole('group', { name: 'Show' })).toBeNull()
  })

  it('says so when what is showing could not be read, and links nothing to a cinema', async () => {
    state.films.mockRejectedValue(new Error('offline'))
    setup('/calendar/cinema?month=2026-11')
    expect(await screen.findByText(/Could not check what is showing at your cinemas/)).toBeTruthy()
    expect(within(month()).getByText('A current first run').closest('a')).toBeNull()
  })

  it('keeps the month in the address and takes it across the switch', async () => {
    setup('/calendar?month=2026-11')
    await within(month()).findByText('A 4K restoration')
    fireEvent.click(screen.getByRole('button', { name: 'Next month' }))
    await waitFor(() => expect(address()).toBe('/calendar?month=2026-12'))
    expect(state.month).toHaveBeenLastCalledWith('2026-12', ['4k_uhd_release', 'blu_ray_release', 'sale_event'])
    expect(await screen.findByText('No disc releases or sales this month')).toBeTruthy()
    fireEvent.click(screen.getByRole('link', { name: 'Cinema releases' }))
    await waitFor(() => expect(address()).toBe('/calendar/cinema?month=2026-12'))
    expect(await screen.findByText('No cinema releases this month')).toBeTruthy()
  })

  it('keeps an admin’s Refresh from TMDB on both calendars, unchanged, and shows a viewer none', async () => {
    setup('/calendar')
    fireEvent.click(screen.getByRole('button', { name: 'Refresh from TMDB' }))
    expect(await screen.findByText(/2 new, 1 moved, 3\s+unchanged/)).toBeTruthy()
    expect(state.ingest).toHaveBeenCalledWith(false)
    cleanup()
    setup('/calendar/cinema')
    expect(screen.getByRole('button', { name: 'Refresh from TMDB' })).toBeTruthy()
    cleanup()
    state.role = 'viewer'
    setup('/calendar/cinema')
    expect(screen.queryByRole('button', { name: 'Refresh from TMDB' })).toBeNull()
  })

  it('gives a link per calendar and one for both from one press, the calendar on screen first', async () => {
    setup('/calendar/cinema?month=2026-11')
    await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Get my calendar links' }).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: 'Get my calendar links' }))
    const groups = await screen.findAllByRole('group', { name: /releases|Both calendars/ })
    expect(groups.map((group) => group.getAttribute('aria-labelledby'))).toEqual(['feed-cinema-releases', 'feed-disc-releases', 'feed-both-calendars'])
    expect(within(groups[0]).getByText(/calendar\.ics\?token=abc&calendar=cinema$/)).toBeTruthy()
    expect(within(groups[1]).getByText(/calendar\.ics\?token=abc&calendar=disc$/)).toBeTruthy()
    expect(within(groups[2]).getByText(/calendar\.ics\?token=abc$/)).toBeTruthy()
    expect(within(groups[1]).getByRole('link', { name: 'Open in Calendar' }).getAttribute('href')).toMatch(/^webcal:.*calendar=disc$/)
    expect(screen.getByText(/only time these links are shown/)).toBeTruthy()
    expect(state.subscribe).toHaveBeenCalledTimes(1)
  })

  it('shows the one link an API from before AC7 gives', async () => {
    state.subscribe.mockResolvedValue({ path: '/api/v1/calendar.ics?token=abc', discPath: null, cinemaPath: null, createdAt: '2026-11-03T17:00:00Z', replacedPrevious: true })
    setup('/calendar')
    await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Get my calendar links' }).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: 'Get my calendar links' }))
    const groups = await screen.findAllByRole('group', { name: /releases|Both calendars/ })
    expect(groups.map((group) => group.getAttribute('aria-labelledby'))).toEqual(['feed-both-calendars'])
    expect(screen.getByText(/Your previous links have stopped working/)).toBeTruthy()
  })

  it('moves Coming soon to the cinema calendar, a film showing at the nine opening its page', async () => {
    state.newReleases.mockResolvedValue({
      basedOnGenres: ['Drama'],
      items: [
        { tmdbId: 2001, title: 'A current first run', releaseDate: '2026-11-05', posterPath: null, overview: '', matchedGenres: ['Drama'], ownership: 'unowned', movieId: null },
        { tmdbId: 4001, title: 'Somewhere else', releaseDate: '2026-12-05', posterPath: null, overview: '', matchedGenres: [], ownership: 'unowned', movieId: null },
      ],
    })
    setup('/calendar/cinema?month=2026-11')
    const soon = await screen.findByRole('region', { name: 'Coming soon' })
    const link = await within(soon).findByRole('link', { name: /A current first run/ })
    expect(link.getAttribute('href')).toBe('/movie-night/cinema/tmdb-2001')
    expect(within(soon).getByText('Somewhere else').closest('a')).toBeNull()
  })
})


function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}

describe('calendar subscription layout readiness (#350)', () => {
  it.each([
    ['cinema', 'month'], ['cinema', 'films'], ['cinema', 'newReleases'],
    ['disc', 'month'], ['disc', 'calendar'],
  ] as const)('holds the native button while %s %s is still loading, then one press creates the links', async (view, source) => {
    const held = deferred<unknown>()
    state[source].mockReturnValue(held.promise)
    setup(`/calendar${view === 'cinema' ? '/cinema' : ''}?month=2026-11`)
    const button = screen.getByRole<HTMLButtonElement>('button', { name: 'Get my calendar links' })
    expect(button.disabled).toBe(true)
    fireEvent.click(button)
    expect(state.subscribe).not.toHaveBeenCalled()
    if (source === 'newReleases') {
      expect(screen.queryByText('Nothing suitable is scheduled')).toBeNull()
      expect(screen.getByText('Looking up cinema releases')).toBeTruthy()
    }
    const value = source === 'month' ? monthOf('2026-11', NOVEMBER)
      : source === 'films' ? filmsFixture()
        : source === 'calendar' ? { items: NOVEMBER, total: NOVEMBER.length, refreshedAt: null }
          : { items: [], basedOnGenres: [] }
    held.resolve(value)
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)
    expect(await screen.findAllByRole('group', { name: /releases|Both calendars/ })).toHaveLength(3)
    expect(state.subscribe).toHaveBeenCalledTimes(1)
    expect(state.month).toHaveBeenCalledTimes(1)
    expect(state.calendar).toHaveBeenCalledTimes(view === 'disc' ? 1 : 0)
    expect(state.newReleases).toHaveBeenCalledTimes(view === 'cinema' ? 1 : 0)
    expect(state.films).toHaveBeenCalledTimes(view === 'cinema' ? 1 : 0)
  })

  it.each(['disc', 'cinema'] as const)('settles failed %s programme reads without permanently blocking a subscription', async view => {
    state.month.mockRejectedValue(new Error('month unavailable'))
    state.calendar.mockRejectedValue(new Error('disc unavailable'))
    state.films.mockRejectedValue(new Error('cinemas unavailable'))
    state.newReleases.mockRejectedValue(new Error('releases unavailable'))
    setup(`/calendar${view === 'cinema' ? '/cinema' : ''}`)
    const button = screen.getByRole<HTMLButtonElement>('button', { name: 'Get my calendar links' })
    await waitFor(() => expect(screen.getByText('The release calendar is unavailable')).toBeTruthy())
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)
    expect(await screen.findAllByRole('group', { name: /releases|Both calendars/ })).toHaveLength(3)
    expect(state.subscribe).toHaveBeenCalledTimes(1)
    expect(screen.queryByText('Nothing suitable is scheduled')).toBeNull()
  })
})


describe('calendar subscription cache and paused reads (#350)', () => {
  it.each(['disc', 'cinema'] as const)('keeps the %s cached window and shares one foreground month read after remount', async view => {
    const route = `/calendar${view === 'cinema' ? '/cinema' : ''}?month=2026-11`
    const client = setup(route)
    await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Get my calendar links' }).disabled).toBe(false))
    cleanup()
    for (const source of ['month', 'calendar', 'films', 'newReleases'] as const) state[source].mockClear()
    setup(route, client)
    await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Get my calendar links' }).disabled).toBe(false))
    expect(state.month).toHaveBeenCalledTimes(1)
    expect(state.films).toHaveBeenCalledTimes(view === 'cinema' ? 1 : 0)
    expect(state.calendar).not.toHaveBeenCalled()
    expect(state.newReleases).not.toHaveBeenCalled()
  })

  it('shows a paused offline cinema programme without a false empty result and settles on reconnect', async () => {
    onlineManager.setOnline(false)
    setup('/calendar/cinema?month=2026-11')
    expect(await screen.findByText('Cinema releases need a connection')).toBeTruthy()
    expect(screen.queryByText('Nothing suitable is scheduled')).toBeNull()
    expect(state.month).not.toHaveBeenCalled()
    expect(state.newReleases).not.toHaveBeenCalled()
    onlineManager.setOnline(true)
    expect(await screen.findByText('Nothing suitable is scheduled')).toBeTruthy()
    await waitFor(() => expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Get my calendar links' }).disabled).toBe(false))
    expect(state.month).toHaveBeenCalledTimes(1)
    expect(state.newReleases).toHaveBeenCalledTimes(1)
  })
})
