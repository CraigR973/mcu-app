// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
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

function renderBar(filters: MovieFilters = {}, onChange = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <FilterBar filters={filters} total={1887} onChange={onChange} trailing={<span>Layout switch</span>} />
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
  const facets = { sections: [], unsectionedItemCount: 0, decades: [], undatedMovieCount: 0 }

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

