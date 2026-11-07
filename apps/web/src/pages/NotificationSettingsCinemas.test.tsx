// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  current: { dealsEnabled: true, saleEventsEnabled: true, releasesEnabled: true, loansEnabled: true,
    movieNightEnabled: true, collectionAdditionsEnabled: true,
    cinemasEnabled: true as boolean | undefined, cinemasOlderOnly: false as boolean | undefined,
    digestMode: false, digestHourLocal: 9, quietHoursStart: null, quietHoursEnd: null, quietHoursTimezone: 'Europe/London' },
  save: vi.fn(),
}))
vi.mock('@/lib/api', async original => ({
  ...(await original<typeof import('@/lib/api')>()),
  fetchNotificationPreferences: () => Promise.resolve(api.current),
  updateNotificationPreferences: (input: { cinemasEnabled?: boolean; cinemasOlderOnly?: boolean }) => {
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
it('saves the independent older-only choice, retaining it while Cinemas is off', async () => {
  api.current.cinemasEnabled = true; api.current.cinemasOlderOnly = false
  show()
  const older = await screen.findByRole('switch', { name: 'Older films only' })
  fireEvent.click(older)
  await waitFor(() => expect(api.save).toHaveBeenCalledWith({ cinemasOlderOnly: true }))
  fireEvent.click(screen.getByRole('switch', { name: 'Cinemas' }))
  await waitFor(() => expect(older.getAttribute('aria-checked')).toBe('true'))
  await waitFor(() => expect(older.hasAttribute('disabled')).toBe(true))
  expect(screen.getByRole('switch', { name: 'Movie night' }).getAttribute('aria-checked')).toBe('true')
})
it('keeps missing older-server fields disabled instead of inventing saved preferences', async () => {
  api.current.cinemasEnabled = undefined; api.current.cinemasOlderOnly = undefined
  show()
  expect(await screen.findByText('Cinema notification settings are not available yet. Reload when connected.')).toBeTruthy()
  expect(screen.getByRole('switch', { name: 'Cinemas' }).hasAttribute('disabled')).toBe(true)
  expect(api.save).not.toHaveBeenCalled()
})
