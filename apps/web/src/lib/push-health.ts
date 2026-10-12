import { fetchPushDeviceStatus, fetchVapidKey, registerPushSubscription } from '@/lib/api'

/**
 * Batch X3 (DS44-02): make this phone's notifications true again, without being asked.
 *
 * **Both phones went silent with nobody told.** Mark's was dropped on its first push (24 Sep)
 * and Craig's on 8 Oct: the push service refused the endpoint, the server deleted the device,
 * and the page, reading only the browser's own subscription, went on saying "Notifications
 * are on for this device". Nothing registered a phone again; the worker's comment said the
 * page did.
 *
 * Now, on every open and whenever the worker reports a subscription change, the page asks the
 * server what it holds for this browser's subscription and acts on the answer:
 *
 * - `live`: nothing to do.
 * - `unknown` (the server lacks it): register this subscription again.
 * - `refused` (the push service refused it): that endpoint is dead, so drop it, take a fresh
 *   subscription and register that.
 * - `removed` (the person took this phone off their list): leave it alone.
 *
 * It never asks for permission: with none granted there is nothing to heal, and a prompt
 * nobody tapped for is the one people dismiss for good. Where the browser will not subscribe
 * without a tap (Safari may not), the answer is `stopped`, and Settings offers Turn on.
 */
export type PushHealth =
  /** No subscription in this browser, or no permission: nothing to heal. */
  | { state: 'none' }
  | { state: 'live' }
  /** The person removed this phone; respected. */
  | { state: 'removed' }
  /** It stopped and could not be mended here; `since` is when, when known. */
  | { state: 'stopped'; since: string | null }

/** RFC 8292 keys travel as unpadded base64url; `applicationServerKey` wants raw bytes.
 *
 *  Built over an explicit `ArrayBuffer` rather than through `Uint8Array.from`, which since
 *  TypeScript 5.7 infers `Uint8Array<ArrayBufferLike>` — a type `applicationServerKey`
 *  rejects, because `ArrayBufferLike` admits a `SharedArrayBuffer` and `BufferSource` does
 *  not. */
export function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  const padded = value.padEnd(value.length + ((4 - (value.length % 4)) % 4), '=')
  const binary = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
  const bytes = new Uint8Array(new ArrayBuffer(binary.length))
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index)
  }
  return bytes
}

/** "iPhone", "Mac", "Windows PC" — a guess the person can overwrite. */
export function guessDeviceLabel(): string {
  const agent = navigator.userAgent
  if (/iPhone/.test(agent)) return 'iPhone'
  if (/iPad/.test(agent)) return 'iPad'
  if (/Android/.test(agent)) return 'Android phone'
  if (/Macintosh/.test(agent)) return 'Mac'
  if (/Windows/.test(agent)) return 'Windows PC'
  return 'This device'
}

/** Whether this browser can hold a push subscription at all, and has been allowed to. */
export function pushPermitted(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    'serviceWorker' in navigator &&
    typeof window !== 'undefined' &&
    'PushManager' in window &&
    typeof Notification !== 'undefined' &&
    Notification.permission === 'granted'
  )
}

/** A fresh subscription for this browser, with the server's current key. */
export async function freshSubscription(registration: ServiceWorkerRegistration): Promise<PushSubscription> {
  const key = await fetchVapidKey()
  if (!key.configured || !key.publicKey) throw new Error('Push is not configured on the server.')
  return registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: base64UrlToBytes(key.publicKey),
  })
}

/** Compare this browser's subscription with the server's devices, and mend what can be. */
export async function healPush(deviceLabel: string = guessDeviceLabel()): Promise<PushHealth> {
  if (!pushPermitted()) return { state: 'none' }
  const registration = await navigator.serviceWorker.ready
  const existing = await registration.pushManager.getSubscription()
  if (!existing) return { state: 'none' }

  const held = await fetchPushDeviceStatus(existing.endpoint)
  if (held.state === 'live') return { state: 'live' }
  if (held.state === 'removed') return { state: 'removed' }
  try {
    let subscription = existing
    if (held.state === 'refused') {
      // A refused endpoint will never be delivered to again; a new one is needed.
      await existing.unsubscribe()
      subscription = await freshSubscription(registration)
    }
    await registerPushSubscription(subscription.toJSON(), deviceLabel)
    return { state: 'live' }
  } catch {
    return { state: 'stopped', since: held.revokedAt }
  }
}
