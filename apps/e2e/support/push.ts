import { createECDH, randomBytes } from 'node:crypto'
import type { Api } from './api.ts'
import { world } from './world.ts'

export interface Device {
  endpoint: string
}

/**
 * A pretend phone for one person: a real P-256 key pair and auth secret, registered through
 * the app's own endpoint, with the private half handed to the fake push service so it can read
 * what the app sends. Returns the endpoint to ask the log about.
 */
export async function registerDevice(api: Api, name: string): Promise<Device> {
  const ecdh = createECDH('prime256v1')
  ecdh.generateKeys()
  const auth = randomBytes(16).toString('base64url')
  const endpoint = `https://push.e2e.example/send/${name}-${randomBytes(4).toString('hex')}`
  await api.post('/notifications/subscriptions', {
    endpoint,
    keys: { p256dh: ecdh.getPublicKey().toString('base64url'), auth },
    deviceLabel: name,
  })
  const existing = (world.scenario().push ?? { keys: {} }) as { keys: Record<string, unknown> }
  world.setScenario({
    push: { keys: { ...existing.keys, [endpoint]: { d: ecdh.getPrivateKey().toString('base64url'), auth } } },
  })
  return { endpoint }
}

export interface Pushed {
  title?: string
  body?: string
  url?: string
  [key: string]: unknown
}

/** What reached this device, oldest first. */
export function pushesTo(device: Device): Pushed[] {
  return world
    .log()
    .filter((c) => c.kind === 'push' && c.endpoint === device.endpoint)
    .map((c) => c.payload as Pushed)
}
