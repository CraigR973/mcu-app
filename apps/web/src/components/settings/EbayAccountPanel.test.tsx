// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { EbayAccount } from '@mcu/shared'

const api = vi.hoisted(() => ({
  fetchEbayAccount: vi.fn(),
  startEbayConnect: vi.fn(),
  disconnectEbay: vi.fn(),
}))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  ...api,
}))

import { EbayAccountPanel } from './EbayAccountPanel'

const NOT_CONNECTED: EbayAccount = {
  configured: true,
  missing: [],
  connected: false,
  accountName: null,
  connectedAt: null,
  note: null,
}

function renderPanel(account: EbayAccount) {
  api.fetchEbayAccount.mockResolvedValue(account)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <EbayAccountPanel />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe('Connect eBay in Settings — Batch T8b', () => {
  it('sends the person to eBay’s own sign-in page', async () => {
    api.startEbayConnect.mockResolvedValue('https://auth.ebay.com/oauth2/authorize?state=abc')
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    renderPanel(NOT_CONNECTED)

    fireEvent.click(await screen.findByRole('button', { name: 'Connect eBay' }))

    await waitFor(() => expect(assign).toHaveBeenCalledWith('https://auth.ebay.com/oauth2/authorize?state=abc'))
    expect(screen.getByText(/this app never sees your eBay password/)).not.toBeNull()
  })

  it('says who is connected, and disconnects only once confirmed', async () => {
    api.disconnectEbay.mockResolvedValue(undefined)
    const confirm = vi.fn(() => true)
    vi.stubGlobal('confirm', confirm)
    renderPanel({ ...NOT_CONNECTED, connected: true, accountName: 'mark_at_the_movies', connectedAt: '2026-10-04T09:00:00Z' })

    expect(await screen.findByText('mark_at_the_movies')).not.toBeNull()
    expect(screen.getByRole('link', { name: /Your eBay lists/ }).getAttribute('href')).toBe('/ebay')
    fireEvent.click(screen.getByRole('button', { name: 'Disconnect' }))

    expect(confirm).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(api.disconnectEbay).toHaveBeenCalledTimes(1))
  })

  it('says when connecting is not set up, naming what is missing', async () => {
    renderPanel({ ...NOT_CONNECTED, configured: false, missing: ['EBAY_RUNAME', 'EBAY_TOKEN_KEY'] })

    expect(await screen.findByText(/not set up on this server yet \(EBAY_RUNAME, EBAY_TOKEN_KEY\)/)).not.toBeNull()
    expect(screen.queryByRole('button', { name: 'Connect eBay' })).toBeNull()
  })

  it('shows why a connection ended', async () => {
    renderPanel({ ...NOT_CONNECTED, note: 'eBay no longer accepts this connection. Connect eBay again.' })

    expect(await screen.findByText('eBay no longer accepts this connection. Connect eBay again.')).not.toBeNull()
  })
})
