// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { EbayTargets } from '@/lib/api'

const { targetsMock, createMock } = vi.hoisted(() => ({
  targetsMock: vi.fn(),
  createMock: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchEbayTargets: targetsMock,
  createSearchTarget: createMock,
}))

import PriceAlertPanel from './PriceAlertPanel'

const FILM = '00000000-0000-4000-8000-000000000051'

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PriceAlertPanel movieId={FILM} title="Star Wars: The Last Jedi" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  targetsMock.mockReset()
  createMock.mockReset()
})
afterEach(cleanup)

describe('PriceAlertPanel — Batch T8a', () => {
  it('asks only for this film’s alerts and lists them', async () => {
    targetsMock.mockResolvedValue({
      items: [
        {
          id: '00000000-0000-4000-8000-000000000052',
          kind: 'search',
          status: 'watching',
          title: 'Star Wars: The Last Jedi',
          movieId: FILM,
          formatCode: 'blu_ray',
          targetPrice: '4.00',
          currency: 'GBP',
          url: null,
          imageUrl: null,
          isAuction: false,
          currentPrice: null,
          currentPostage: null,
          currentUrl: null,
          endsAt: null,
          lastCheckedAt: null,
          metAt: null,
          lastError: null,
          createdAt: '2026-09-26T09:00:00Z',
        },
      ],
      lastRun: null,
    } satisfies EbayTargets)
    renderPanel()
    expect(await screen.findByText('Blu-ray at £4.00')).toBeTruthy()
    expect(targetsMock).toHaveBeenCalledWith(FILM)
  })

  it('sets an alert on the format chosen, at the price typed', async () => {
    targetsMock.mockResolvedValue({ items: [], lastRun: null } satisfies EbayTargets)
    createMock.mockResolvedValue({})
    renderPanel()
    fireEvent.change(await screen.findByRole('combobox'), { target: { value: 'blu_ray' } })
    fireEvent.change(screen.getByPlaceholderText('10.00'), { target: { value: '6.50' } })
    fireEvent.click(screen.getByRole('button', { name: /Alert me/ }))
    await waitFor(() => expect(createMock).toHaveBeenCalledWith(FILM, 'blu_ray', '6.50'))
  })
})
