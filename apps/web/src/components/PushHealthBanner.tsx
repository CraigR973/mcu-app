import { useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BellOff } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { PushSubscriptionList } from '@mcu/shared'

import { fetchPushSubscriptions } from '@/lib/api'
import { healPush } from '@/lib/push-health'
import { formatDayMonth } from '@/lib/utils'

/**
 * Batch X3 (DS44-02): mend this phone's notifications on open, and say so when they stopped.
 *
 * On every open of the app, and whenever the service worker reports a subscription change,
 * the shell compares this browser's subscription with the server's devices and registers
 * the phone again where it can (`lib/push-health.ts`). Before X3 nothing did, and both
 * phones went silent with nobody told.
 *
 * When a person's last device was refused by the push service and none is live, a banner
 * stays until they turn notifications on again; the daily check names it to Craig as well.
 */
export function PushHealthBanner() {
  const queryClient = useQueryClient()
  const devices = useQuery({ queryKey: ['push-subscriptions'], queryFn: fetchPushSubscriptions })

  useEffect(() => {
    let cancelled = false
    const heal = async () => {
      try {
        const health = await healPush()
        if (!cancelled && health.state === 'live') {
          await queryClient.invalidateQueries({ queryKey: ['push-subscriptions'] })
        }
      } catch {
        // Offline, or the server busy: the next open tries again, and Settings says how it is.
      }
    }
    void heal()
    if (!('serviceWorker' in navigator)) return () => void (cancelled = true)
    const onMessage = (event: MessageEvent) => {
      if ((event.data as { type?: string } | null)?.type === 'mcu-push-subscription-changed') {
        void heal()
      }
    }
    navigator.serviceWorker.addEventListener('message', onMessage)
    return () => {
      cancelled = true
      navigator.serviceWorker.removeEventListener('message', onMessage)
    }
  }, [queryClient])

  return devices.data ? <PushStoppedNotice devices={devices.data} /> : null
}

export function PushStoppedNotice({ devices }: { devices: PushSubscriptionList }) {
  if (devices.total > 0 || !devices.stoppedAt) return null
  return (
    <div
      role="status"
      className="flex items-start gap-2 border-b border-warning/40 bg-warning/12 px-4 py-2 text-sm text-foreground"
    >
      <BellOff className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
      <p>
        Notifications stopped reaching your phone on {formatDayMonth(devices.stoppedAt)}.{' '}
        <Link to="/settings" className="font-semibold underline underline-offset-2">
          Turn them on again
        </Link>
      </p>
    </div>
  )
}
