// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import RetailersPage from './RetailersPage'

const auth = vi.hoisted(() => ({ role: 'admin' as 'admin' | 'viewer' }))
vi.mock('@/context/auth', () => ({
  useAuth: () => ({ profile: { id: 'p1', displayName: 'Craig', role: auth.role } }),
}))

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
  auth.role = 'admin'
})

/**
 * Batch 22b. A check captured on 30 Sep from the real route, run in-process against
 * production read-only over the Zavvi and Second Sight sale pages captured on 28-30 Sep —
 * with Powerhouse's line as the runner words a refused page, since its page was not
 * captured.
 */
const checked = {
  dryRun: true,
  written: 5,
  retailersWithDeals: 2,
  skippedOwned: 7,
  outcomes: [
    {
      retailer: 'Powerhouse Films', ok: false, found: 16, kept: 0, skippedOwned: 0, rejected: 0,
      matched: 0, notDiscounted: 0, rejectedReasons: [],
      pageReasons: ["no card on the page has a 'was' price — the sale-price selector has probably moved, which turns a sale page into a price list"],
      error: "no card on the page has a 'was' price — the sale-price selector has probably moved, which turns a sale page into a price list",
    },
    {
      retailer: 'Second Sight', ok: true, found: 16, kept: 1, skippedOwned: 0, rejected: 0,
      matched: 0, notDiscounted: 15, pageReasons: [], rejectedReasons: [], error: null,
    },
    {
      retailer: 'Zavvi', ok: true, found: 12, kept: 4, skippedOwned: 7, rejected: 0,
      matched: 7, notDiscounted: 1, pageReasons: [], rejectedReasons: [], error: null,
    },
  ],
}

function stubDealsApi(saved: object = { ...checked, dryRun: false }) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/deals/scrape?dryRun=true')) return new Response(JSON.stringify(checked))
    if (url.includes('/deals/scrape?dryRun=false')) return new Response(JSON.stringify(saved))
    if (url.includes('/scrapers/built-in')) {
      return new Response(JSON.stringify({ items: [], unverified: [] }))
    }
    return new Response(JSON.stringify({
      items: [], total: 0, enabledCount: 0, configuredCount: 0,
    }))
  })
  vi.stubGlobal('fetch', fetchMock)
  const asked = (dryRun: boolean) =>
    fetchMock.mock.calls.some(([input]) =>
      String(input).includes(`/deals/scrape?dryRun=${String(dryRun)}`),
    )
  return { asked }
}

describe('RetailersPage — checking the sale pages (Batch 22b)', () => {
  it('checks without saving, and shows the three numbers and each shop', async () => {
    const { asked } = stubDealsApi()
    renderPage()

    // "Save deals" is not offered until a check has come back.
    expect(screen.queryByRole('button', { name: 'Save deals' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Check sale pages' }))

    expect(await screen.findByText('Checked. Nothing is saved yet.')).not.toBeNull()
    expect(screen.getByText('deals to save').nextElementSibling?.textContent).toBe('5')
    expect(screen.getByText('shops with deals').nextElementSibling?.textContent).toBe('2')
    expect(screen.getByText('already owned, skipped').nextElementSibling?.textContent).toBe('7')
    expect(screen.getByText('16 found · 1 kept · 15 not discounted')).not.toBeNull()
    expect(
      screen.getByText('12 found · 4 kept · 7 already owned · 1 not discounted'),
    ).not.toBeNull()
    expect(screen.getByRole('button', { name: 'Save deals' })).not.toBeNull()
    expect(asked(true)).toBe(true)
    expect(asked(false)).toBe(false)
  })

  it('says why a shop kept nothing, once', async () => {
    stubDealsApi()
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Check sale pages' }))

    // Counts and the page's reason, not the same sentence twice via `error`.
    expect(await screen.findByText('16 found · 0 kept')).not.toBeNull()
    expect(screen.getAllByText(/no card on the page has a 'was' price/)).toHaveLength(1)
  })

  it('saves only when asked twice, then reports what was saved', async () => {
    const { asked } = stubDealsApi()
    const confirm = vi.fn(() => false)
    vi.stubGlobal('confirm', confirm)
    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Check sale pages' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Save deals' }))
    expect(confirm).toHaveBeenCalledTimes(1)
    expect(asked(false)).toBe(false)

    confirm.mockReturnValue(true)
    fireEvent.click(screen.getByRole('button', { name: 'Save deals' }))

    expect(await screen.findByText('Saved.')).not.toBeNull()
    expect(screen.getByText('deals saved').nextElementSibling?.textContent).toBe('5')
    expect(asked(false)).toBe(true)
    // Saving again needs a fresh check.
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Save deals' })).toBeNull()
    })
  })

  it('is not offered to a viewer', () => {
    auth.role = 'viewer'
    stubDealsApi()
    renderPage()

    expect(screen.queryByRole('button', { name: 'Check sale pages' })).toBeNull()
  })
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
