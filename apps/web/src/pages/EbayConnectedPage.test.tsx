// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ finishEbayConnect: vi.fn() }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))

import EbayConnectedPage from './EbayConnectedPage'

function Address() {
  const location = useLocation()
  return <output aria-label="Address">{location.pathname + location.search}</output>
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <EbayConnectedPage />
        <Address />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Where eBay sends a person back — Batch T8b', () => {
  it('hands the code and state to the API once, and says who is connected', async () => {
    api.finishEbayConnect.mockResolvedValue({
      configured: true,
      missing: [],
      connected: true,
      accountName: 'mark_at_the_movies',
      connectedAt: '2026-10-04T09:00:00Z',
      note: null,
    })
    renderAt('/settings/ebay/connected?state=the-state&code=v%5E1.1%23code&expires_in=299')

    expect(await screen.findByText('mark_at_the_movies')).not.toBeNull()
    expect(api.finishEbayConnect).toHaveBeenCalledTimes(1)
    expect(api.finishEbayConnect).toHaveBeenCalledWith('v^1.1#code', 'the-state')
    // The code leaves the address bar as soon as it is read.
    expect(screen.getByLabelText('Address').textContent).toBe('/settings/ebay/connected')
    expect(screen.getByRole('link', { name: 'Your eBay lists' }).getAttribute('href')).toBe('/ebay')
  })

  it('says what went wrong, with the API’s own words', async () => {
    api.finishEbayConnect.mockRejectedValue(new Error('This eBay sign-in took over ten minutes. Press Connect eBay again.'))
    renderAt('/settings/ebay/connected?state=the-state&code=c')

    expect(await screen.findByText('This eBay sign-in took over ten minutes. Press Connect eBay again.')).not.toBeNull()
    expect(screen.getByRole('link', { name: 'Back to Settings' }).getAttribute('href')).toBe('/settings?tab=ebay')
  })

  it('asks nothing of the API when eBay sent no code', async () => {
    renderAt('/settings/ebay/connected')

    expect(await screen.findByText(/eBay did not send a sign-in code back/)).not.toBeNull()
    expect(api.finishEbayConnect).not.toHaveBeenCalled()
  })
})
