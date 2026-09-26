import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BellOff,
  BellRing,
  Clock,
  Laptop,
  Loader2,
  Send,
  Smartphone,
  Trash2,
  TriangleAlert,
} from 'lucide-react'
import type { NotificationPreference, PushSubscriptionRecord } from '@mcu/shared'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  fetchNotificationPreferences,
  fetchNotifications,
  fetchPushSubscriptions,
  notificationStateLabel,
  removePushSubscription,
  sendTestNotification,
  updateNotificationPreferences,
  type NotificationPreferenceInput,
} from '@/lib/api'
import { usePushSubscription } from '@/hooks/usePushSubscription'
import { listState, queryErrorMessage } from '@/lib/query-state'
import { cn } from '@/lib/utils'

/** §6.1's categories, in the order they are worth reading. */
const CATEGORIES: Array<{
  key: keyof Pick<
    NotificationPreference,
    | 'dealsEnabled'
    | 'saleEventsEnabled'
    | 'releasesEnabled'
    | 'loansEnabled'
    | 'movieNightEnabled'
  >
  label: string
  description: string
}> = [
  {
    key: 'dealsEnabled',
    label: 'Deals',
    description: 'A disc on your wanted list drops below the price you set.',
  },
  {
    key: 'saleEventsEnabled',
    label: 'Sale seasons',
    description: 'Two weeks before Black Friday, Prime Day, Boxing Day and the rest.',
  },
  {
    key: 'releasesEnabled',
    label: 'Upcoming releases',
    description: 'A week before something on your calendar comes out.',
  },
  {
    key: 'loansEnabled',
    label: 'Overdue loans',
    description: 'A disc you lent out is past its due date.',
  },
  {
    key: 'movieNightEnabled',
    label: 'Movie night',
    description: 'Votes and matches while a movie night is running.',
  },
]

/**
 * **The knob is anchored to the track's left edge** (Batch U3's browser check). Without
 * `left-0` an absolute child of a `<button>` starts where the button centres its content,
 * so at 375 px the knob of every switch that was on sat past the end of its track and over
 * the card's edge. The two translations assume that anchor.
 */
export function Toggle({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  disabled?: boolean
  label: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'touch-hit relative h-6 w-11 shrink-0 rounded-full border transition-colors disabled:opacity-50',
        checked ? 'border-success bg-success' : 'border-input bg-muted',
      )}
    >
      <span
        className={cn(
          'absolute left-0 top-0.5 h-5 w-5 rounded-full border border-input bg-background shadow transition-transform',
          checked ? 'translate-x-5' : 'translate-x-0.5',
        )}
      />
    </button>
  )
}

/**
 * Turning push on for **this** browser, and listing the ones already on.
 *
 * Every unavailable state gets its own sentence. Batch 9 dropped this wizard step rather
 * than ship a button that did nothing (`DECISIONS.md` #50); the way not to repeat that is
 * for the UI to be able to say precisely which part is missing.
 */
function DeviceSection() {
  const queryClient = useQueryClient()
  const push = usePushSubscription()
  const [label, setLabel] = useState('')
  const [testResult, setTestResult] = useState<string | null>(null)

  useEffect(() => {
    setLabel((current) => current || push.suggestedLabel)
  }, [push.suggestedLabel])

  const devices = useQuery({
    queryKey: ['push-subscriptions'],
    queryFn: fetchPushSubscriptions,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['push-subscriptions'] })

  const enable = useMutation({
    mutationFn: () => push.subscribe(label.trim() || push.suggestedLabel),
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: (id: string) => removePushSubscription(id),
    onSuccess: invalidate,
  })
  const test = useMutation({
    mutationFn: (id: string) => sendTestNotification(id),
    onSuccess: (result) => {
      // Three different problems, three different sentences — see the schema's note.
      setTestResult(
        result.delivered > 0
          ? 'Sent. If nothing appeared, check notification permissions for this site.'
          : result.subscriptionsRemoved > 0
            ? 'That device is no longer reachable and has been removed.'
            : 'The push service would not accept it. Try turning notifications off and on again.',
      )
      void invalidate()
    },
    onError: (error) => setTestResult(queryErrorMessage(error, 'Could not send a test.')),
  })

  const state = listState(devices, (devices.data?.items.length ?? 0) === 0)

  return (
    <section className="rounded-lg border border-border p-4">
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <BellRing className="h-5 w-5" aria-hidden />
        Devices
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Each browser you turn notifications on in gets its own entry. Removing one leaves
        the others alone.
      </p>

      {push.state === 'unsupported' && (
        <p className="mt-3 rounded bg-warning/12 p-3 text-sm text-warning">
          This browser cannot receive push notifications. On an iPhone, add the app to your
          home screen first — Safari only allows push from an installed app.
        </p>
      )}
      {push.state === 'server-not-configured' && (
        <p className="mt-3 flex items-start gap-2 rounded bg-destructive/12 p-3 text-sm text-destructive">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          Push is not configured on the server — no VAPID key is set. Nothing this page
          does will reach a device until it is.
        </p>
      )}
      {push.state === 'denied' && (
        <p className="mt-3 rounded bg-warning/12 p-3 text-sm text-warning">
          Notifications are blocked for this site in your browser settings. That has to be
          changed there — the app cannot ask again.
        </p>
      )}
      {push.error && (
        <p className="mt-3 text-sm text-destructive">{push.error}</p>
      )}

      {(push.state === 'available' || push.state === 'checking') && (
        <div className="mt-4 flex flex-wrap items-end gap-2">
          <label className="text-sm">
            <span className="mb-1 block text-muted-foreground">
              Name this device
            </span>
            <Input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              maxLength={100}
              placeholder={push.suggestedLabel}
            />
          </label>
          <Button
            onClick={() => enable.mutate()}
            disabled={push.busy || push.state === 'checking'}
          >
            {push.busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <BellRing className="mr-2 h-4 w-4" aria-hidden />
            )}
            Turn on for this device
          </Button>
        </div>
      )}

      {push.state === 'subscribed' && (
        <div className="mt-4 flex items-center gap-2">
          <span className="text-sm text-success">
            Notifications are on for this device.
          </span>
          <Button variant="outline" onClick={() => void push.unsubscribe()} disabled={push.busy}>
            <BellOff className="mr-2 h-4 w-4" aria-hidden />
            Turn off here
          </Button>
        </div>
      )}

      <div className="mt-4">
        {state === 'loading' && (
          <p className="text-sm text-muted-foreground">Loading devices…</p>
        )}
        {state === 'offline' && (
          <p className="text-sm text-muted-foreground">Waiting for the network…</p>
        )}
        {state === 'error' && (
          <p className="text-sm text-destructive">
            {queryErrorMessage(devices.error, 'Could not load your devices.')}
          </p>
        )}
        {state === 'empty' && (
          <p className="text-sm text-muted-foreground">No devices are registered yet.</p>
        )}
        {state === 'ready' && (
          <ul className="divide-y divide-border">
            {devices.data?.items.map((device: PushSubscriptionRecord) => (
              <li key={device.id} className="flex items-center gap-3 py-3">
                {/iPhone|iPad|Android/i.test(device.userAgent ?? '') ? (
                  <Smartphone className="h-4 w-4 text-muted-foreground" aria-hidden />
                ) : (
                  <Laptop className="h-4 w-4 text-muted-foreground" aria-hidden />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">
                    {device.deviceLabel ?? 'Unnamed device'}
                  </p>
                  <p className="truncate text-xs text-muted-foreground">
                    {device.pushService} · {device.endpointPreview}
                    {device.lastUsedAt
                      ? ` · last push ${new Date(device.lastUsedAt).toLocaleDateString()}`
                      : ' · never used'}
                    {device.failureCount > 0 ? ` · ${device.failureCount} failures` : ''}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => test.mutate(device.id)}
                  disabled={test.isPending}
                  aria-label={`Send a test notification to ${device.deviceLabel ?? 'this device'}`}
                >
                  <Send className="mr-1 h-3 w-3" aria-hidden />
                  Test
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => remove.mutate(device.id)}
                  disabled={remove.isPending}
                  aria-label={`Remove ${device.deviceLabel ?? 'this device'}`}
                >
                  <Trash2 className="h-3 w-3" aria-hidden />
                </Button>
              </li>
            ))}
          </ul>
        )}
        {testResult && <p className="mt-2 text-sm text-muted-foreground">{testResult}</p>}
      </div>
    </section>
  )
}

function PreferencesSection() {
  const queryClient = useQueryClient()
  const preferences = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: fetchNotificationPreferences,
  })

  const save = useMutation({
    mutationFn: (input: NotificationPreferenceInput) => updateNotificationPreferences(input),
    onSuccess: (updated) => {
      queryClient.setQueryData(['notification-preferences'], updated)
    },
  })

  const current = preferences.data
  if (preferences.isPending) {
    return <p className="text-sm text-muted-foreground">Loading your preferences…</p>
  }
  if (!current) {
    return (
      <p className="text-sm text-destructive">
        {queryErrorMessage(preferences.error, 'Could not load your preferences.')}
      </p>
    )
  }

  const quietHoursOn = current.quietHoursStart !== null && current.quietHoursEnd !== null

  return (
    <section className="rounded-lg border border-border p-4">
      <h2 className="text-lg font-semibold">What you hear about</h2>
      <ul className="mt-3 divide-y divide-border">
        {CATEGORIES.map((category) => (
          <li key={category.key} className="flex items-center gap-4 py-3">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{category.label}</p>
              <p className="text-sm text-muted-foreground">
                {category.description}
              </p>
            </div>
            <Toggle
              label={category.label}
              checked={current[category.key]}
              disabled={save.isPending}
              onChange={(next) => save.mutate({ [category.key]: next })}
            />
          </li>
        ))}
      </ul>

      <h2 className="mt-6 flex items-center gap-2 text-lg font-semibold">
        <Clock className="h-5 w-5" aria-hidden />
        When
      </h2>

      <div className="mt-3 flex items-center gap-4 py-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium">Daily digest</p>
          <p className="text-sm text-muted-foreground">
            Hold everything and send one summary a day instead.
          </p>
        </div>
        <Toggle
          label="Daily digest"
          checked={current.digestMode}
          disabled={save.isPending}
          onChange={(next) => save.mutate({ digestMode: next })}
        />
      </div>

      {current.digestMode && (
        <label className="mt-2 block text-sm">
          <span className="mb-1 block text-muted-foreground">
            Digest hour (local time)
          </span>
          <Input
            type="number"
            min={0}
            max={23}
            className="w-24"
            value={current.digestHourLocal}
            onChange={(event) =>
              save.mutate({ digestHourLocal: Number(event.target.value) })
            }
          />
        </label>
      )}

      <div className="mt-4 flex items-center gap-4 py-2">
        <div className="min-w-0 flex-1">
          <p className="font-medium">Quiet hours</p>
          <p className="text-sm text-muted-foreground">
            Nothing arrives between these times. Anything raised during them waits until
            they end — it is not thrown away.
          </p>
        </div>
        <Toggle
          label="Quiet hours"
          checked={quietHoursOn}
          disabled={save.isPending}
          onChange={(next) =>
            save.mutate(
              next
                ? { quietHoursStart: '22:00:00', quietHoursEnd: '07:00:00' }
                : { clearQuietHours: true },
            )
          }
        />
      </div>

      {quietHoursOn && (
        <div className="mt-2 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-muted-foreground">From</span>
            <Input
              type="time"
              value={(current.quietHoursStart ?? '22:00:00').slice(0, 5)}
              onChange={(event) =>
                save.mutate({
                  quietHoursStart: `${event.target.value}:00`,
                  quietHoursEnd: current.quietHoursEnd ?? '07:00:00',
                })
              }
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-muted-foreground">Until</span>
            <Input
              type="time"
              value={(current.quietHoursEnd ?? '07:00:00').slice(0, 5)}
              onChange={(event) =>
                save.mutate({
                  quietHoursStart: current.quietHoursStart ?? '22:00:00',
                  quietHoursEnd: `${event.target.value}:00`,
                })
              }
            />
          </label>
          <p className="pb-2 text-xs text-muted-foreground">
            Times are {current.quietHoursTimezone}, so they follow British Summer Time.
          </p>
        </div>
      )}

      {save.isError && (
        <p className="mt-3 text-sm text-destructive">
          {queryErrorMessage(save.error, 'Could not save that.')}
        </p>
      )}
    </section>
  )
}

/** The outbox — the page that answers "why did I not get that". */
function HistorySection() {
  const notifications = useQuery({
    queryKey: ['notifications'],
    queryFn: () => fetchNotifications(25),
  })
  const state = listState(notifications, (notifications.data?.items.length ?? 0) === 0)

  return (
    <section className="rounded-lg border border-border p-4">
      <h2 className="text-lg font-semibold">Recent notifications</h2>
      {state === 'loading' && <p className="mt-2 text-sm text-muted-foreground">Loading…</p>}
      {state === 'offline' && (
        <p className="mt-2 text-sm text-muted-foreground">Waiting for the network…</p>
      )}
      {state === 'error' && (
        <p className="mt-2 text-sm text-destructive">
          {queryErrorMessage(notifications.error, 'Could not load your notifications.')}
        </p>
      )}
      {state === 'empty' && (
        <p className="mt-2 text-sm text-muted-foreground">Nothing has been sent yet.</p>
      )}
      {state === 'ready' && (
        <ul className="mt-2 divide-y divide-border">
          {notifications.data?.items.map((item) => (
            <li key={item.id} className="py-3">
              <p className="font-medium">{item.title}</p>
              <p className="text-sm text-muted-foreground">{item.body}</p>
              <p
                className={cn(
                  'mt-1 text-xs',
                  item.status === 'sent'
                    ? 'text-success'
                    : item.status === 'failed'
                      ? 'text-destructive'
                      : 'text-muted-foreground',
                )}
              >
                {notificationStateLabel(item)}
                {item.deliverAfter
                  ? ` · due ${new Date(item.deliverAfter).toLocaleString()}`
                  : ''}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** The notification settings, without page chrome — Batch S3 folded this page into
 *  `/settings` as one of two tabs, so the heading is the tab's job now. `/settings/notifications`
 *  still resolves; it redirects. */
export function NotificationSettings() {
  return (
    <div className="space-y-6">
      <DeviceSection />
      <PreferencesSection />
      <HistorySection />
    </div>
  )
}
