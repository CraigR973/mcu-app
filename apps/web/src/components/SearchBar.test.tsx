// @vitest-environment happy-dom
import { onlineManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { fetchSearchMock, fetchSearchBeyondMock } = vi.hoisted(() => ({
  fetchSearchMock: vi.fn(),
  fetchSearchBeyondMock: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchSearch: fetchSearchMock,
  fetchSearchBeyond: fetchSearchBeyondMock,
}))

import SearchBar from './SearchBar'

function LocationProbe() {
  const location = useLocation()
  return <output aria-label="Current page">{location.pathname}</output>
}

function renderSearchBar(props: Parameters<typeof SearchBar>[0] = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SearchBar {...props} />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const HEAT = {
  id: '11111111-1111-4111-8111-111111111111', title: 'Heat', originalTitle: null,
  year: 1995, posterPath: null, backdropPath: null, tmdbRating: 8.3,
  runtimeMinutes: 170, bestFormatOwned: '4k_uhd', bestHdrOwned: null,
  bestAudioOwned: null, identified: true, copyCount: 2,
  locations: [{ section: 'Front', shelf: '2nd', label: 'Front 2nd' }], watched: true,
  lastWatchedAt: '2025-03-12',
}

const HEAT_WAVE = {
  tmdbId: 10001, title: 'Heat Wave', year: 1990, posterPath: null, overview: '',
  movieId: null, lastWatchedAt: null, streamingOn: ['Netflix', 'MUBI'], streamingChecked: true,
  maybeOwned: null,
}

async function typeQuery(value: string) {
  fireEvent.change(screen.getByRole('combobox', { name: 'Search films' }), { target: { value } })
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 300)) })
}

afterEach(() => {
  cleanup()
})

beforeEach(() => {
  fetchSearchMock.mockReset()
  fetchSearchBeyondMock.mockReset().mockResolvedValue({ query: 'heat', items: [], unavailable: false })
})

describe('SearchBar', () => {
  it('focuses and selects its input on mcu:focus-search — the "/" shortcut now dispatches this rather than owning the keydown itself', () => {
    renderSearchBar()
    const input = screen.getByLabelText('Search films') as HTMLInputElement

    window.dispatchEvent(new Event('mcu:focus-search'))

    expect(document.activeElement).toBe(input)
  })

  it('exposes the global lookup as a collapsed combobox', () => {
    renderSearchBar()
    expect(screen.getByRole('combobox', { name: 'Search films' }).getAttribute('aria-expanded')).toBe('false')
  })

  it('supports keyboard selection and exposes ownership, copies and shelf', async () => {
    fetchSearchMock.mockResolvedValue({
      query: 'heat', total: 1, items: [{
        id: '11111111-1111-4111-8111-111111111111', title: 'Heat', originalTitle: null,
        year: 1995, posterPath: null, backdropPath: null, tmdbRating: 8.3,
        runtimeMinutes: 170, bestFormatOwned: '4k_uhd', bestHdrOwned: null,
        bestAudioOwned: null, identified: true, copyCount: 2,
        locations: [{ section: 'Front', shelf: '2nd', label: 'Front 2nd' }], watched: true,
      }],
    })
    renderSearchBar()
    const input = screen.getByRole('combobox', { name: 'Search films' })
    fireEvent.change(input, { target: { value: 'heat' } })
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 300)) })

    const option = await screen.findByRole('option', { name: /Heat.*Owned.*4K UHD.*2 copies.*Front 2nd/i })
    // `waitFor`, not a bare assertion, and the distinction is a race rather than a
    // preference. `SearchBar` sets `activeIndex` in a `useEffect` keyed on
    // `[query, results.length]`, so the option is in the DOM one render *before* it is
    // selected. `findByRole` resolves on the earlier render, and whether the effect has
    // flushed by the time the next line runs is a matter of machine speed: this failed
    // roughly one local run in eight and failed in CI on a slower runner.
    //
    // The assertion is unchanged — still `aria-selected === 'true'`, still the same
    // element. Only the waiting is added.
    await waitFor(() => expect(option.getAttribute('aria-selected')).toBe('true'))
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    await waitFor(() => expect(option.getAttribute('aria-selected')).toBe('true'))
  })

  it('never presents a failed lookup as no owned results', async () => {
    fetchSearchMock.mockRejectedValue(new Error('network failed'))
    renderSearchBar()
    fireEvent.change(screen.getByRole('combobox', { name: 'Search films' }), { target: { value: 'heat' } })
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 300)) })

    expect((await screen.findByRole('alert')).textContent).toMatch(/could not be searched/i)
    expect(screen.queryByText(/No owned films found/i)).toBeNull()
  })

  it('still closes its own dropdown on Escape', () => {
    renderSearchBar()
    const input = screen.getByLabelText('Search films') as HTMLInputElement
    input.focus()

    fireEvent.keyDown(document, { key: 'Escape' })

    expect(document.activeElement).not.toBe(input)
  })

  it('says when you last watched each owned film, and when you have not', async () => {
    fetchSearchMock.mockResolvedValue({
      query: 'heat', total: 2,
      items: [HEAT, { ...HEAT, id: '22222222-2222-4222-8222-222222222222', title: 'Heat 2', watched: false, lastWatchedAt: null }],
    })
    renderSearchBar()
    await typeQuery('heat')

    expect(await screen.findByRole('option', { name: /^Heat 1995.*Seen 12 Mar 2025/ })).not.toBeNull()
    expect(screen.getByRole('option', { name: /Heat 2.*Not seen/ })).not.toBeNull()
  })

  it('follows owned films with the ones not in the collection, and where they stream', async () => {
    fetchSearchMock.mockResolvedValue({ query: 'heat', total: 1, items: [HEAT] })
    fetchSearchBeyondMock.mockResolvedValue({ query: 'heat', items: [HEAT_WAVE], unavailable: false })
    renderSearchBar()
    await typeQuery('heat')

    const beyond = await screen.findByRole('group', { name: 'Not in the collection' })
    expect(within(beyond).getByRole('option', { name: /Heat Wave.*Streaming on Netflix, MUBI/ })).not.toBeNull()
    const options = screen.getAllByRole('option')
    expect(options.map((option) => option.textContent?.split(/\d/)[0])).toEqual(['Heat', 'Heat Wave'])
  })

  it('moves through both groups with the arrow keys', async () => {
    fetchSearchMock.mockResolvedValue({ query: 'heat', total: 1, items: [HEAT] })
    fetchSearchBeyondMock.mockResolvedValue({ query: 'heat', items: [HEAT_WAVE], unavailable: false })
    renderSearchBar()
    await typeQuery('heat')
    const wave = await screen.findByRole('option', { name: /Heat Wave/ })

    fireEvent.keyDown(screen.getByRole('combobox', { name: 'Search films' }), { key: 'ArrowDown' })
    await waitFor(() => expect(wave.getAttribute('aria-selected')).toBe('true'))
  })

  it('opens the card for a film with no page here, and the page for one that has one', async () => {
    fetchSearchMock.mockResolvedValue({ query: 'heat', total: 0, items: [] })
    fetchSearchBeyondMock.mockResolvedValue({
      query: 'heat', unavailable: false,
      items: [HEAT_WAVE, { ...HEAT_WAVE, tmdbId: 10002, title: 'Heatwave Diaries', movieId: '33333333-3333-4333-8333-333333333333' }],
    })
    renderSearchBar()
    await typeQuery('heat')
    fireEvent.click(await screen.findByRole('option', { name: /^Heat Wave/ }))
    expect(screen.getByLabelText('Current page').textContent).toBe('/films/tmdb/10001')

    await typeQuery('heat')
    fireEvent.click(await screen.findByRole('option', { name: /wave Diaries/ }))
    expect(screen.getByLabelText('Current page').textContent).toBe('/movies/33333333-3333-4333-8333-333333333333')
  })

  it('flags a film that might be an unidentified copy on the shelf', async () => {
    fetchSearchMock.mockResolvedValue({ query: 'african queen', total: 0, items: [] })
    fetchSearchBeyondMock.mockResolvedValue({
      query: 'african queen', unavailable: false,
      items: [{ ...HEAT_WAVE, tmdbId: 488, title: 'The African Queen', maybeOwned: { movieId: '44444444-4444-4444-8444-444444444444', title: 'African Queen, The' } }],
    })
    renderSearchBar()
    await typeQuery('african queen')

    expect(await screen.findByRole('option', { name: /Might be your copy of “African Queen, The”/ })).not.toBeNull()
  })

  it('hands a pick to the page that embedded it instead of navigating', async () => {
    const onPickOwned = vi.fn()
    const onPickBeyond = vi.fn()
    fetchSearchMock.mockResolvedValue({ query: 'heat', total: 1, items: [HEAT] })
    fetchSearchBeyondMock.mockResolvedValue({ query: 'heat', items: [HEAT_WAVE], unavailable: false })
    renderSearchBar({ onPickOwned, onPickBeyond })
    await typeQuery('heat')

    fireEvent.click(await screen.findByRole('option', { name: /^Heat 1995/ }))
    expect(onPickOwned).toHaveBeenCalledWith(expect.objectContaining({ id: HEAT.id }))
    await typeQuery('heat')
    fireEvent.click(await screen.findByRole('option', { name: /Heat Wave/ }))
    expect(onPickBeyond).toHaveBeenCalledWith(expect.objectContaining({ tmdbId: 10001 }))
    expect(screen.getByLabelText('Current page').textContent).toBe('/')
  })

  it('keeps your own films when TMDB does not answer, and says so', async () => {
    fetchSearchMock.mockResolvedValue({ query: 'heat', total: 1, items: [HEAT] })
    fetchSearchBeyondMock.mockResolvedValue({ query: 'heat', items: [], unavailable: true })
    renderSearchBar()
    await typeQuery('heat')

    expect(await screen.findByText(/TMDB didn't answer, so only your own films are shown/)).not.toBeNull()
    expect(screen.getByRole('option', { name: /^Heat 1995/ })).not.toBeNull()
  })

  it('leaves the "/" shortcut to the app-wide search', () => {
    renderSearchBar({ global: false, label: 'Search for a film to suggest' })
    const input = screen.getByLabelText('Search for a film to suggest')

    window.dispatchEvent(new Event('mcu:focus-search'))

    expect(document.activeElement).not.toBe(input)
  })

  it('offline, keeps cached owned results and says films beyond the shelf need a connection', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['search', 'heat'], { query: 'heat', total: 1, items: [HEAT] })
    onlineManager.setOnline(false)
    try {
      render(
        <QueryClientProvider client={client}>
          <MemoryRouter>
            <SearchBar />
          </MemoryRouter>
        </QueryClientProvider>,
      )
      await typeQuery('heat')

      expect(await screen.findByText(/Films outside the collection need a connection/)).not.toBeNull()
      expect(screen.getByRole('option', { name: /^Heat 1995/ })).not.toBeNull()
      expect(fetchSearchBeyondMock).not.toHaveBeenCalled()
    } finally {
      onlineManager.setOnline(true)
    }
  })
})

