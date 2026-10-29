// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  current: { dealsEnabled: true, saleEventsEnabled: true, releasesEnabled: true, loansEnabled: true,
    movieNightEnabled: true, collectionAdditionsEnabled: true as boolean | undefined,
    digestMode: false, digestHourLocal: 9, quietHoursStart: null, quietHoursEnd: null, quietHoursTimezone: 'Europe/London' },
  save: vi.fn(),
}))
vi.mock('@/lib/api', async original => ({
  ...(await original<typeof import('@/lib/api')>()),
  fetchNotificationPreferences: () => Promise.resolve(api.current),
  updateNotificationPreferences: (input: { collectionAdditionsEnabled: boolean }) => {
    api.save(input)
    return Promise.resolve({ ...api.current, ...input })
  },
}))
const { PreferencesSection } = await import('./NotificationSettingsPage')
afterEach(() => { cleanup(); vi.clearAllMocks() })
function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PreferencesSection /></QueryClientProvider>)
}
it('shows the approved wording, saves only this toggle and reflects the returned preference', async () => {
  api.current.collectionAdditionsEnabled = true
  show()
  const toggle = await screen.findByRole('switch', { name: "Mark's additions" })
  expect(toggle.getAttribute('aria-checked')).toBe('true')
  expect(screen.getByText('When Mark adds the first owned copy of a film or series. Extra copies and editions stay quiet.')).toBeTruthy()
  fireEvent.click(toggle)
  await waitFor(() => expect(api.save).toHaveBeenCalledWith({ collectionAdditionsEnabled: false }))
  await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('false'))
})
it('keeps an older response unavailable instead of inventing a preference', async () => {
  api.current.collectionAdditionsEnabled = undefined
  show()
  expect(await screen.findByText('Unavailable — refresh settings')).toBeTruthy()
  expect(screen.queryByRole('switch', { name: "Mark's additions" })).toBeNull()
  expect(api.save).not.toHaveBeenCalled()
})
