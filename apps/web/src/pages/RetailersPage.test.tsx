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
  it('says so when the format priced is not the one wanted', async () => {
    // A fallback is allowed, but a maxPrice alert compares against whatever was priced —
    // so a Blu-ray want answered with a 4K disc has to be visible in the report.
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/scrapers/built-in')) {
        return new Response(JSON.stringify({ items: [], unverified: [] }))
      }
      if (url.includes('/scrapers/run')) {
        return new Response(JSON.stringify({
          outcomes: [{
            retailer: 'Zavvi',
            wantedTitle: 'Jaws',
            ok: true,
            price: '19.99',
            currency: 'GBP',
            substitutedFormat: '4k_uhd',
            editionMatched: false,
            skipped: false,
            notStocked: false,
            url: 'https://www.zavvi.com/p/4k/jaws/1/',
            reasons: [],
            error: null,
          }],
          succeeded: 1,
          failed: 0,
          skipped: 0,
          notStocked: 0,
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

    expect(await screen.findByText(/Not the format wanted — priced the 4K UHD/)).not.toBeNull()
  })

  it('reads a not-stocked answer as an answer, not as a failure', async () => {
    // A boutique label asked for a film it does not carry answers properly and says no.
    // Reporting that in the red of a broken scraper is what made three working shops look
    // broken on 2026-09-09.
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/scrapers/built-in')) {
        return new Response(JSON.stringify({ items: [], unverified: [] }))
      }
      if (url.includes('/scrapers/run')) {
        return new Response(JSON.stringify({
          outcomes: [{
            retailer: 'Second Sight',
            wantedTitle: 'Misery',
            ok: false,
            price: null,
            currency: null,
            substitutedFormat: null,
            editionMatched: null,
            skipped: false,
            notStocked: true,
            url: null,
            reasons: ["page title 'Cold Prey Trilogy' has nothing in common with 'Misery'"],
            error: 'Second Sight does not stock Misery',
          }],
          succeeded: 0,
          failed: 0,
          skipped: 0,
          notStocked: 1,
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

    expect(await screen.findByText(/Not stocked here/)).not.toBeNull()
    // Counted apart from failures, and the raw title-guard reason is not paraded as an error.
    expect(await screen.findByText(/0 failed, 1 not stocked/)).not.toBeNull()
  })

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
            substitutedFormat: null,
            editionMatched: null,
            skipped: false,
            notStocked: false,
            url: 'https://www.zavvi.com/p/the-fall-guy/1/',
            reasons: [],
            error: null,
          }],
          succeeded: 1,
          failed: 0,
          skipped: 0,
          notStocked: 0,
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
