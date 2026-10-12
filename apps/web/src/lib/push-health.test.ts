import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  fetchPushDeviceStatus: vi.fn(),
  fetchVapidKey: vi.fn(),
  registerPushSubscription: vi.fn(),
}))
vi.mock('@/lib/api', () => api)

const { healPush } = await import('./push-health')

/** A browser subscription that records being dropped. */
function subscription(endpoint: string) {
  return {
    endpoint,
    unsubscribe: vi.fn().mockResolvedValue(true),
    toJSON: () => ({ endpoint, keys: { p256dh: 'p', auth: 'a' } }),
  }
}

function browser(existing: ReturnType<typeof subscription> | null, permission = 'granted') {
  const fresh = subscription('https://push.example/fresh')
  const pushManager = {
    getSubscription: vi.fn().mockResolvedValue(existing),
    subscribe: vi.fn().mockResolvedValue(fresh),
  }
  vi.stubGlobal('navigator', {
    userAgent: 'iPhone',
    serviceWorker: { ready: Promise.resolve({ pushManager }) },
  })
  vi.stubGlobal('window', { PushManager: class {} })
  vi.stubGlobal('Notification', { permission })
  return { pushManager, fresh }
}

beforeEach(() => {
  for (const mock of Object.values(api)) mock.mockReset()
  api.fetchVapidKey.mockResolvedValue({ configured: true, publicKey: 'AQAB' })
  api.registerPushSubscription.mockResolvedValue({})
})
afterEach(() => vi.unstubAllGlobals())

describe('healPush — Batch X3 (DS44-02)', () => {
  it('does nothing when the server holds this phone live', async () => {
    browser(subscription('https://push.example/live'))
    api.fetchPushDeviceStatus.mockResolvedValue({ state: 'live', revokedAt: null })
    expect(await healPush()).toEqual({ state: 'live' })
    expect(api.registerPushSubscription).not.toHaveBeenCalled()
  })

  it('registers this subscription again when the server lacks it', async () => {
    const existing = subscription('https://push.example/forgotten')
    const { pushManager } = browser(existing)
    api.fetchPushDeviceStatus.mockResolvedValue({ state: 'unknown', revokedAt: null })

    expect(await healPush()).toEqual({ state: 'live' })

    expect(pushManager.subscribe).not.toHaveBeenCalled()
    expect(api.registerPushSubscription).toHaveBeenCalledWith(existing.toJSON(), 'iPhone')
  })

  it('takes a fresh subscription when the old endpoint was refused', async () => {
    const existing = subscription('https://push.example/refused')
    const { pushManager, fresh } = browser(existing)
    api.fetchPushDeviceStatus.mockResolvedValue({ state: 'refused', revokedAt: '2026-10-08T00:21:00Z' })

    expect(await healPush()).toEqual({ state: 'live' })

    expect(existing.unsubscribe).toHaveBeenCalled()
    expect(pushManager.subscribe).toHaveBeenCalled()
    expect(api.registerPushSubscription).toHaveBeenCalledWith(fresh.toJSON(), 'iPhone')
  })

  it('says when it stopped if the browser will not subscribe without a tap', async () => {
    const { pushManager } = browser(subscription('https://push.example/refused'))
    pushManager.subscribe.mockRejectedValue(new Error('NotAllowedError'))
    api.fetchPushDeviceStatus.mockResolvedValue({ state: 'refused', revokedAt: '2026-10-08T00:21:00Z' })

    expect(await healPush()).toEqual({ state: 'stopped', since: '2026-10-08T00:21:00Z' })
  })

  it('leaves a phone the person removed alone', async () => {
    browser(subscription('https://push.example/removed'))
    api.fetchPushDeviceStatus.mockResolvedValue({ state: 'removed', revokedAt: '2026-10-01T00:00:00Z' })
    expect(await healPush()).toEqual({ state: 'removed' })
    expect(api.registerPushSubscription).not.toHaveBeenCalled()
  })

  it('never asks for permission, and has nothing to heal without it or a subscription', async () => {
    browser(subscription('https://push.example/x'), 'default')
    expect(await healPush()).toEqual({ state: 'none' })
    browser(null)
    expect(await healPush()).toEqual({ state: 'none' })
    expect(api.fetchPushDeviceStatus).not.toHaveBeenCalled()
  })
})
