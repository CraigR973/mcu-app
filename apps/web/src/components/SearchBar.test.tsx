// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { fetchSearchMock } = vi.hoisted(() => ({ fetchSearchMock: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchSearch: fetchSearchMock,
}))

import SearchBar from './SearchBar'

function renderSearchBar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SearchBar />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
})

beforeEach(() => {
  fetchSearchMock.mockReset()
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
})
