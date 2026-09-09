// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import RetailersPage from './RetailersPage'

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <RetailersPage />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('RetailersPage', () => {
  it('runs a live preview and shows the result without claiming a row was saved', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/scrapers/built-in')) {
        return new Response(JSON.stringify({ items: [], unverified: [] }))
      }
      if (url.includes('/scrapers/run')) {
        return new Response(JSON.stringify({
          outcomes: [{
            retailer: 'Zavvi',
            wantedTitle: 'The Fall Guy',
            ok: true,
            price: '19.99',
            currency: 'GBP',
            url: 'https://www.zavvi.com/p/the-fall-guy/1/',
            reasons: [],
            error: null,
          }],
          succeeded: 1,
          failed: 0,
          written: 0,
          disabled: [],
          dryRun: true,
        }))
      }
      return new Response(JSON.stringify({
        items: [], total: 0, enabledCount: 0, configuredCount: 0,
      }))
    })
    vi.stubGlobal('fetch', fetchMock)
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Preview live run' }))

    expect(await screen.findByText(/Preview complete: 1 passed, 0 failed, 0 price rows saved/)).not.toBeNull()
    // Rendered as money in the currency it was read in, never as a bare number: the
    // shape guard's whole job is to prove the currency, so the report must show it.
    expect(await screen.findByText(/£19\.99/)).not.toBeNull()
    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([input]) =>
        String(input).includes('/scrapers/run?dryRun=true'),
      )).toBe(true)
    })
  })
})
