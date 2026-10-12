// @vitest-environment happy-dom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const push = vi.hoisted(() => ({
  value: {
    state: 'subscribed' as string,
    stoppedSince: null as string | null,
    error: null,
    busy: false,
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    suggestedLabel: 'iPhone',
  },
}))
const devices = vi.hoisted(() => ({
  value: { items: [] as unknown[], total: 0, stoppedAt: null as string | null },
}))
vi.mock('@/hooks/usePushSubscription', () => ({ usePushSubscription: () => push.value }))
vi.mock('@/lib/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api')>()),
  fetchPushSubscriptions: vi.fn(() => Promise.resolve(devices.value)),
}))

const { DeviceSection } = await import('./NotificationSettingsPage')

function renderDevices() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <DeviceSection />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)

describe('Settings, this device — Batch X3 (DS44-02)', () => {
  it('says notifications are on only when the server holds this phone live', async () => {
    push.value = { ...push.value, state: 'subscribed', stoppedSince: null }
    devices.value = { items: [], total: 0, stoppedAt: null }
    renderDevices()
    expect(await screen.findByText('Notifications are on for this device.')).toBeTruthy()
  })

  it('says when this phone stopped, and offers to turn them on again', async () => {
    push.value = { ...push.value, state: 'stopped', stoppedSince: '2026-10-08T00:21:00Z' }
    devices.value = { items: [], total: 0, stoppedAt: '2026-10-08T00:21:00Z' }
    renderDevices()
    expect(
      await screen.findByText(
        'This phone stopped getting notifications on 8 Oct. Turn them on again.',
      ),
    ).toBeTruthy()
    expect(screen.queryByText('Notifications are on for this device.')).toBeNull()
    expect(screen.getByRole('button', { name: /Turn on again/ })).toBeTruthy()
  })

  it('says so from the account when this browser holds nothing but the last device was refused', async () => {
    push.value = { ...push.value, state: 'available', stoppedSince: null }
    devices.value = { items: [], total: 0, stoppedAt: '2026-09-24T09:00:00Z' }
    renderDevices()
    expect(
      await screen.findByText(
        'This phone stopped getting notifications on 24 Sep. Turn them on again.',
      ),
    ).toBeTruthy()
  })
})
