// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchFacets: vi.fn().mockResolvedValue({ sections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0 }),
}))

import { fetchFacets, type MovieFilters } from '@/lib/api'

import { FilterBar } from './FilterBar'

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

/** The phone's back gesture, as far as the router can tell. */
function BackGesture() {
  const navigate = useNavigate()
  return <button type="button" onClick={() => navigate(-1)}>Swipe back</button>
}

function renderBar(filters: MovieFilters = {}, onChange = vi.fn(), context: 'browse' | 'saved' = 'browse') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/home', '/movies']} initialIndex={1}>
        <FilterBar filters={filters} total={1887} onChange={onChange} context={context} trailing={<span>Layout switch</span>} />
        <BackGesture />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return onChange
}

describe('FilterBar — Batch T3', () => {
  it('keeps Filters, Sort, the count and the layout switch in one row, and the count once', () => {
    renderBar()
    const row = within(screen.getByTestId('collection-controls-row'))

    expect(row.getByRole('button', { name: /Filters/ })).not.toBeNull()
    expect(row.getByRole('combobox', { name: /Sort collection/ })).not.toBeNull()
    expect(row.getByText('Layout switch')).not.toBeNull()
    expect(screen.getAllByText(/1,887/)).toHaveLength(1)
  })

  it('applies a runtime range after a pause, as one change', async () => {
    vi.useFakeTimers()
    const onChange = renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))

    fireEvent.change(screen.getByLabelText('Shortest runtime in minutes'), { target: { value: '90' } })
    fireEvent.change(screen.getByLabelText('Longest runtime in minutes'), { target: { value: '120' } })
    expect(onChange).not.toHaveBeenCalled()
    await act(async () => { vi.advanceTimersByTime(600) })

    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith({ runtimeMin: 90, runtimeMax: 120 })
  })

  it('never applies a range whose shortest is longer than its longest', async () => {
    vi.useFakeTimers()
    const onChange = renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))

    fireEvent.change(screen.getByLabelText('Shortest runtime in minutes'), { target: { value: '150' } })
    fireEvent.change(screen.getByLabelText('Longest runtime in minutes'), { target: { value: '90' } })
    await act(async () => { vi.advanceTimersByTime(600) })

    expect(screen.getByRole('alert').textContent).toMatch(/shortest can't be longer/)
    expect(onChange).not.toHaveBeenCalled()
  })

  it('shows a runtime range as a chip that clears it', () => {
    const onChange = renderBar({ runtimeMin: 90, runtimeMax: 120 })

    fireEvent.click(screen.getByRole('button', { name: 'Remove 90–120 min filter' }))

    expect(onChange).toHaveBeenCalledWith({ runtimeMin: undefined, runtimeMax: undefined })
  })
})

describe('FilterBar — Batch T7', () => {
  const facets = { sections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0, allSections: [] }

  it('hides the spec filters while no disc has specs, because nothing could match them', async () => {
    vi.mocked(fetchFacets).mockResolvedValueOnce({ ...facets, discsWithSpecs: 0 })
    renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))
    await screen.findByRole('group', { name: /runtime/i })
    expect(screen.queryByRole('group', { name: 'Technical specification filters' })).toBeNull()
  })

  it('shows them once a disc has specs', async () => {
    vi.mocked(fetchFacets).mockResolvedValueOnce({ ...facets, discsWithSpecs: 12 })
    renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))
    const group = await screen.findByRole('group', { name: 'Technical specification filters' })
    expect(within(group).getByRole('button', { name: 'Dolby Vision' })).not.toBeNull()
  })
})

describe('FilterBar — Batch V4', () => {
  it("lists only the sections that hold a disc, not the whole vocabulary the form gets", async () => {
    vi.mocked(fetchFacets).mockResolvedValueOnce({
      sections: [{ section: 'Front', movieCount: 3, itemCount: 3, shelves: [] }],
      unsectionedItemCount: 0,
      decades: [],
      undatedMovieCount: 0,
      discsWithSpecs: 0,
      allSections: ['Front', 'Back', "Craig's house"],
    })
    renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))

    const select = await screen.findByRole('combobox', { name: 'Filter by section' })
    await within(select).findByRole('option', { name: 'Front (3)' })
    const options = within(select).getAllByRole('option').map((option) => option.textContent)
    expect(options).toEqual(['All locations', 'Front (3)'])
  })
})

describe('FilterBar — the Lounge’s sides, Mark 14 Oct', () => {
  it('offers the Lounge’s sides as sides, with what each holds, and names the chip so', async () => {
    vi.mocked(fetchFacets).mockResolvedValueOnce({
      sections: [
        {
          section: 'Lounge',
          movieCount: 164,
          itemCount: 164,
          shelfNoun: 'side',
          shelves: [
            { shelf: 'Left', label: 'Left hand side', movieCount: 68, itemCount: 68 },
            { shelf: 'Right', label: 'Right hand side', movieCount: 96, itemCount: 96 },
          ],
        },
      ],
      unsectionedItemCount: 0,
      decades: [],
      undatedMovieCount: 0,
      discsWithSpecs: 0,
      allSections: ['Lounge'],
    })
    renderBar({ section: 'Lounge', shelf: 'Right' })
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))

    const select = await screen.findByRole('combobox', { name: 'Filter by side' })
    const options = within(select).getAllByRole('option').map((option) => option.textContent)
    expect(options).toEqual(['Both sides', 'Left hand side (68)', 'Right hand side (96)'])
    expect(screen.getByText('Side: Right hand side')).not.toBeNull()
  })
})

describe('FilterBar — still to identify, Mark 14 Oct', () => {
  const facets = { sections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0, discsWithSpecs: 0, allSections: [] }

  it('offers the films still to identify, with how many, and applies it', async () => {
    vi.mocked(fetchFacets).mockResolvedValueOnce({ ...facets, toIdentifyMovieCount: 155 })
    const onChange = renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))

    const select = await screen.findByRole('combobox', { name: 'Filter by identified or not' })
    expect(within(select).getByRole('option', { name: 'Still to identify (155)' })).not.toBeNull()
    fireEvent.change(select, { target: { value: 'true' } })

    expect(onChange).toHaveBeenCalledWith({ toIdentify: true })
  })

  it('shows as a chip that clears it', () => {
    const onChange = renderBar({ toIdentify: true })

    fireEvent.click(screen.getByRole('button', { name: 'Remove Still to identify filter' }))

    expect(onChange).toHaveBeenCalledWith({ toIdentify: undefined })
  })

  it('hides while every film is identified', async () => {
    vi.mocked(fetchFacets).mockResolvedValueOnce({ ...facets, toIdentifyMovieCount: 0 })
    renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))

    await screen.findByRole('combobox', { name: 'Filter by watched status' })
    expect(screen.queryByRole('combobox', { name: 'Filter by identified or not' })).toBeNull()
  })
})

describe('FilterBar — in doubt, Batch Y4', () => {
  const facets = { sections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0, discsWithSpecs: 0, allSections: [] }

  it('offers the films in doubt, with how many, and applies it in place of "Still to identify"', async () => {
    vi.mocked(fetchFacets).mockResolvedValueOnce({ ...facets, toIdentifyMovieCount: 12, inDoubtMovieCount: 362 })
    const onChange = renderBar({ toIdentify: true })
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))

    const select = await screen.findByRole('combobox', { name: 'Filter by identified or not' })
    expect(await within(select).findByRole('option', { name: 'In doubt (362)' })).not.toBeNull()
    fireEvent.change(select, { target: { value: 'in-doubt' } })

    expect(onChange).toHaveBeenCalledWith({ toIdentify: undefined, inDoubt: true })
  })

  it('shows when only films in doubt remain, without "Still to identify (0)"', async () => {
    vi.mocked(fetchFacets).mockResolvedValueOnce({ ...facets, toIdentifyMovieCount: 0, inDoubtMovieCount: 3 })
    renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))

    const select = await screen.findByRole('combobox', { name: 'Filter by identified or not' })
    expect(within(select).getByRole('option', { name: 'In doubt (3)' })).not.toBeNull()
    expect(within(select).queryByRole('option', { name: /Still to identify/ })).toBeNull()
  })

  it('shows as a chip that clears it', () => {
    const onChange = renderBar({ inDoubt: true })

    fireEvent.click(screen.getByRole('button', { name: 'Remove In doubt filter' }))

    expect(onChange).toHaveBeenCalledWith({ inDoubt: undefined })
  })
})

describe('FilterBar — reaching the films on a phone, Mark 15 Oct', () => {
  // happy-dom's window is 1024px wide: below 1280px, where the open panel is a history entry.
  it('ends the open panel in a button that shows the films, and closes it', () => {
    renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))
    expect(screen.getByLabelText('Filter by genre')).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Show 1,887 films' }))

    expect(screen.queryByLabelText('Filter by genre')).toBeNull()
    expect(screen.getByRole('button', { name: /Filters/ }).getAttribute('aria-expanded')).toBe('false')
  })

  it('closes the panel on the back gesture rather than leaving the Archive', () => {
    renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))
    expect(screen.getByLabelText('Filter by genre')).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Swipe back' }))

    expect(screen.queryByLabelText('Filter by genre')).toBeNull()
    // Still on the Archive: the panel was the entry back took away.
    expect(screen.getByTestId('collection-controls-row')).not.toBeNull()
  })

  it('keeps a filter picked inside the panel when it closes', () => {
    const onChange = renderBar()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))
    fireEvent.change(screen.getByLabelText('Filter by genre'), { target: { value: '27' } })
    expect(onChange).toHaveBeenCalledWith({ genreId: 27 })

    fireEvent.click(screen.getByRole('button', { name: 'Show 1,887 films' }))
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('leaves a saved collection’s editor as it was: no history entry and no Show button', () => {
    renderBar({}, vi.fn(), 'saved')
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))

    expect(screen.getByLabelText('Filter by genre')).not.toBeNull()
    expect(screen.queryByRole('button', { name: /^Show / })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /Filters/ }))
    expect(screen.queryByLabelText('Filter by genre')).toBeNull()
  })
})
