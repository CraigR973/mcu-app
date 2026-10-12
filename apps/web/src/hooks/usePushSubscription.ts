import { useCallback, useEffect, useState } from 'react'

import { fetchVapidKey, registerPushSubscription } from '@/lib/api'
import { base64UrlToBytes, guessDeviceLabel, healPush } from '@/lib/push-health'

/**
 * Turning browser push on and off for **this** device — §6.2's per-device half.
 *
 * **Every step of this can fail in a way the browser does not explain**, which is why the
 * state below is a named union rather than a boolean. `usePwaInstall` learned the same
 * lesson in Batch 9: the onboarding wizard's notifications step read a global that nothing
 * set, and offered to enable push against no infrastructure at all (`DECISIONS.md` #50).
 * A hook that can only say "on" or "off" ends up lying in at least three situations —
 * permission denied at the OS level, the server having no VAPID key, and Safari refusing
 * to subscribe outside an installed PWA.
 */
export type PushState =
  /** Still working out what this browser and server can do. */
  | 'checking'
  /** No `PushManager` — desktop Safari before 16.4, and every browser in an iframe. */
  | 'unsupported'
  /** The API has no VAPID key. The **TMDB shape**: the feature is absent from the
   *  deployment, and without this state the UI could not say so. */
  | 'server-not-configured'
  /** The person said no. Only they can undo it, in browser settings. */
  | 'denied'
  /** Supported, permitted or not yet asked, and not currently subscribed. */
  | 'available'
  /** This device holds a subscription **the server holds live** (Batch X3: before X3 the
   *  browser's word alone said so, above "No devices are registered yet"). */
  | 'subscribed'
  /** This phone stopped getting notifications and could not be mended without a tap
   *  (Batch X3). `stoppedSince` says when, when the server knows. */
  | 'stopped'

export interface UsePushSubscription {
  state: PushState
  /** With `stopped`: when the push service refused this phone, if known. */
  stoppedSince: string | null
  error: string | null
  busy: boolean
  subscribe: (deviceLabel: string) => Promise<void>
  unsubscribe: () => Promise<void>
  /** A sensible default label, so the field is never empty on a phone. */
  suggestedLabel: string
}

export function usePushSubscription(): UsePushSubscription {
  const [state, setState] = useState<PushState>('checking')
  const [stoppedSince, setStoppedSince] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
      setState('unsupported')
      return
    }
    if (Notification.permission === 'denied') {
      setState('denied')
      return
    }
    try {
      const key = await fetchVapidKey()
      if (!key.configured || !key.publicKey) {
        setState('server-not-configured')
        return
      }
      const registration = await navigator.serviceWorker.ready
      const existing = await registration.pushManager.getSubscription()
      if (!existing) {
        setState('available')
        return
      }
      // Batch X3: the server's word, not the browser's, and mended where it can be.
      const health = await healPush()
      if (health.state === 'live') {
        setState('subscribed')
      } else if (health.state === 'stopped') {
        setStoppedSince(health.since)
        setState('stopped')
      } else {
        setState('available')
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not check notifications')
      setState('available')
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  /**
   * The service worker cannot re-register a rotated subscription on its own — the access
   * token lives in the page, not in the worker — so it asks any open page to do it, and the
   * refresh below does (Batch X3: before it, the refresh only re-read local state).
   */
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return
    const onMessage = (event: MessageEvent) => {
      if ((event.data as { type?: string } | null)?.type === 'mcu-push-subscription-changed') {
        void refresh()
      }
    }
    navigator.serviceWorker.addEventListener('message', onMessage)
    return () => navigator.serviceWorker.removeEventListener('message', onMessage)
  }, [refresh])

  const subscribe = useCallback(async (deviceLabel: string) => {
    setBusy(true)
    setError(null)
    try {
      const key = await fetchVapidKey()
      if (!key.configured || !key.publicKey) {
        setState('server-not-configured')
        return
      }

      // Asked here rather than on page load: a permission prompt that appears without the
      // person having clicked anything is the one they reflexively dismiss, and a denial
      // is permanent from the app's side.
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        setState(permission === 'denied' ? 'denied' : 'available')
        return
      }

      const registration = await navigator.serviceWorker.ready
      let subscription = await registration.pushManager.getSubscription()
      if (subscription && state === 'stopped') {
        // Batch X3: the old endpoint was refused; it will never be delivered to again.
        await subscription.unsubscribe()
        subscription = null
      }
      subscription ??= await registration.pushManager.subscribe({
        // Required by every browser: a push that any server could send would be spam.
        userVisibleOnly: true,
        applicationServerKey: base64UrlToBytes(key.publicKey),
      })

      await registerPushSubscription(subscription.toJSON(), deviceLabel)
      setStoppedSince(null)
      setState('subscribed')
    } catch (cause) {
      // Safari throws here when the site is not an installed PWA, with a message that
      // does not say so. Surfacing the raw text beats swallowing it.
      setError(cause instanceof Error ? cause.message : 'Could not enable notifications')
    } finally {
      setBusy(false)
    }
  }, [state])

  const unsubscribe = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.getSubscription()
      if (subscription) {
        // Unsubscribe locally first: if the server call fails afterwards the row is
        // revoked on the next `410`, whereas the reverse order can leave the browser
        // subscribed to an endpoint the server has forgotten.
        await subscription.unsubscribe()
      }
      setState('available')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not turn notifications off')
    } finally {
      setBusy(false)
    }
  }, [])

  return {
    state,
    stoppedSince,
    error,
    busy,
    subscribe,
    unsubscribe,
    suggestedLabel: guessDeviceLabel(),
  }
}

// Exported for the tests. `base64UrlToBytes` is the one pure function in this file whose
// failure mode is silent: a wrong byte produces a subscription the server can encrypt to
// and no browser can decrypt, with a `201` from the push service either way.
export { base64UrlToBytes, guessDeviceLabel }
