// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { NotificationRecord } from '@mcu/shared'

// AC5 (#345): cinema trips share the Movie night switch, whose description Craig approved.
const current = {
  dealsEnabled: true, saleEventsEnabled: true, releasesEnabled: true, loansEnabled: true,
  movieNightEnabled: true, collectionAdditionsEnabled: true, digestMode: false, digestHourLocal: 9,
  quietHoursStart: null, quietHoursEnd: null, quietHoursTimezone: 'Europe/London',
}
vi.mock('@/lib/api', async (original) => ({
  ...(await original<typeof import('@/lib/api')>()),
  fetchNotificationPreferences: () => Promise.resolve(current),
}))
const { PreferencesSection } = await import('./NotificationSettingsPage')
const { notificationStateLabel } = await import('@/lib/api')
afterEach(() => { cleanup(); vi.clearAllMocks() })

it('keeps the switch’s label and says it covers cinema trips', async () => {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PreferencesSection /></QueryClientProvider>)
  expect(await screen.findByRole('switch', { name: 'Movie night' })).toBeTruthy()
  expect(screen.getByText('Movie nights and cinema trips: invitations, replies, changes and reminders.')).toBeTruthy()
  expect(screen.queryByText('Votes and matches while a movie night is running.')).toBeNull()
})

it('says a reminder held past the showing was not sent, and why', () => {
  const reminder: NotificationRecord = {
    id: '0a3282b1-50db-4af9-8d94-513dc8dd4bc3', category: 'movie_night', status: 'suppressed',
    title: 'Cinema today: Wild Horse Nine', body: '20:10 at ODEON Glasgow Quay, with Mark.', url: null,
    createdAt: '2026-11-09T08:00:00Z', deliverAfter: null, deferredReason: null, suppressedReason: 'too_late',
    sentAt: null, deliveredCount: 0,
  }
  expect(notificationStateLabel(reminder)).toBe('Not sent — it would have arrived after the showing')
  expect(notificationStateLabel({ ...reminder, suppressedReason: 'category_disabled' })).toBe('Not sent — that category is switched off')
})
