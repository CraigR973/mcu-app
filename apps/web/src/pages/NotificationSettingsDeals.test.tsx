// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

// AG6 (#383): each person may choose to hear only of Wanted-list deals.
const api = vi.hoisted(() => ({
  current: { dealsEnabled: true, saleEventsEnabled: true, releasesEnabled: true, loansEnabled: true,
    movieNightEnabled: true, collectionAdditionsEnabled: true, cinemasEnabled: true, cinemasOlderOnly: false,
    dealsWantedOnly: false as boolean | undefined,
    digestMode: false, digestHourLocal: 9, quietHoursStart: '22:00:00', quietHoursEnd: '07:00:00', quietHoursTimezone: 'Europe/London' },
  save: vi.fn(),
}))
vi.mock('@/lib/api', async original => ({
  ...(await original<typeof import('@/lib/api')>()),
  fetchNotificationPreferences: () => Promise.resolve(api.current),
  updateNotificationPreferences: (input: { dealsEnabled?: boolean; dealsWantedOnly?: boolean }) => {
    api.save(input)
    api.current = { ...api.current, ...input }
    return Promise.resolve(api.current)
  },
}))
const { PreferencesSection } = await import('./NotificationSettingsPage')
afterEach(() => { cleanup(); vi.clearAllMocks() })
function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PreferencesSection /></QueryClientProvider>)
}

it('saves Wanted list only, and says what the Deals switch now sends', async () => {
  api.current.dealsEnabled = true; api.current.dealsWantedOnly = false
  show()
  const only = await screen.findByRole('switch', { name: 'Wanted list only' })
  expect(only.getAttribute('aria-checked')).toBe('false')
  expect(screen.getByText(/Other eBay upgrades come in one summary at 18:00/)).toBeTruthy()
  fireEvent.click(only)
  await waitFor(() => expect(api.save).toHaveBeenCalledWith({ dealsWantedOnly: true }))
  await waitFor(() => expect(only.getAttribute('aria-checked')).toBe('true'))
})

it('cannot be changed while Deals is off, and keeps what was chosen', async () => {
  api.current.dealsEnabled = false; api.current.dealsWantedOnly = true
  show()
  const only = await screen.findByRole('switch', { name: 'Wanted list only' })
  expect(only.hasAttribute('disabled')).toBe(true)
  expect(only.getAttribute('aria-checked')).toBe('true')
})

it('is not offered by an API a deploy behind', async () => {
  api.current.dealsEnabled = true; api.current.dealsWantedOnly = undefined
  show()
  await screen.findByRole('switch', { name: 'Cinemas' })
  expect(screen.queryByRole('switch', { name: 'Wanted list only' })).toBeNull()
})
