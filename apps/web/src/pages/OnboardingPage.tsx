import { useEffect, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Check, Loader2, Moon, Sun } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/auth'
import { useTheme } from '@/context/theme'
import { usePushSubscription } from '@/hooks/usePushSubscription'
import { usePwaInstall } from '@/hooks/usePwaInstall'
import { completeOnboarding, fetchMovies } from '@/lib/api'

/**
 * The setup wizard — phase 2.8, rebuilt rather than repaired.
 *
 * Batch 3 removed the April version entirely: its completion flag was a Supabase column
 * that no longer exists, so porting it would have shipped a wizard that appears to work
 * and saves nothing (`DECISIONS.md` #27). Migration `010` gives it a real column.
 *
 * **Three of the eight original steps are gone, because this batch's acceptance criterion
 * is that every step does what it says.**
 *
 * - **Email connect** — Stage 10 is dropped, and this app has no email addresses at all:
 *   sign-in is a display name and a PIN (`DECISIONS.md` #11). The step displayed
 *   `user.email` from a field that cannot exist.
 * - **Notifications** — dropped in Batch 9 and **restored here in Batch 11**, which is
 *   the debt `DECISIONS.md` #50 recorded against this batch. The April version offered
 *   six toggles for features that did not exist, never requested notification permission
 *   and created no subscription, against no VAPID key and no `push_subscriptions` table.
 *   All four now exist, and the step asks for exactly one thing — permission for this
 *   device — with the categories left to the settings page, where they can be changed
 *   again later.
 * - **Import** — the catalogue is loaded by a CLI script the owner runs, not by anything
 *   a person does in here. What remains of the step is a statement of what is in the
 *   collection, which is true and useful.
 *
 * The install step **does** have infrastructure now: Batch 8 shipped the manifest and the
 * service worker, so `beforeinstallprompt` can fire and {@link usePwaInstall} catches it.
 */

/**
 * Turn on push for this device — the step Batch 9 removed.
 *
 * **It asks for one thing and states what it cannot do.** Every unavailable case gets its
 * own sentence rather than a disabled button: an iPhone that has not been added to the
 * home screen, a browser where permission was already refused, and a server with no VAPID
 * key are three different problems with three different answers, and the April version
 * showed the same toggle for all of them.
 *
 * Skippable, always. Notifications are the one part of setup that is genuinely optional,
 * and a wizard that will not advance without a permission grant teaches people to grant
 * permissions to get past wizards.
 */
function NotificationsStep() {
  const push = usePushSubscription()
  const [label, setLabel] = useState('')

  useEffect(() => {
    setLabel((current) => current || push.suggestedLabel)
  }, [push.suggestedLabel])

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Notifications</h2>
      <p className="text-sm text-muted-foreground">
        A price drop on something you want, a sale season starting, a disc you lent out
        going overdue. You can change exactly which of those reach you afterwards, in
        Settings.
      </p>

      {push.state === 'subscribed' && (
        <p className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
          <Check className="h-4 w-4" aria-hidden />
          Notifications are on for this device.
        </p>
      )}
      {push.state === 'unsupported' && (
        <p className="text-sm text-muted-foreground">
          This browser cannot receive notifications. On an iPhone, add the app to your home
          screen first — Safari only allows them from an installed app.
        </p>
      )}
      {push.state === 'denied' && (
        <p className="text-sm text-muted-foreground">
          Notifications are blocked for this site in your browser settings. That has to be
          changed there; the app cannot ask again.
        </p>
      )}
      {push.state === 'server-not-configured' && (
        <p className="text-sm text-muted-foreground">
          Notifications are not set up on the server yet, so there is nothing to turn on
          here. Nothing else in the app is affected.
        </p>
      )}
      {push.state === 'available' && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">
            <span className="mb-1 block text-muted-foreground">Name this device</span>
            <input
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              maxLength={100}
              placeholder={push.suggestedLabel}
              className="rounded border border-input bg-background px-3 py-2 text-sm"
            />
          </label>
          <Button
            onClick={() => void push.subscribe(label.trim() || push.suggestedLabel)}
            disabled={push.busy}
          >
            {push.busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />}
            Turn on notifications
          </Button>
        </div>
      )}
      {push.error && <p className="text-sm text-destructive">{push.error}</p>}
      <p className="text-xs text-muted-foreground">You can skip this and set it up later.</p>
    </div>
  )
}

interface StepDef {
  id: string
  label: string
  node: ReactNode
}

const STEP_KEY = 'mcu:onboarding-step'

function Welcome({ isAdmin, name }: { isAdmin: boolean; name: string }) {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Welcome, {name}</h2>
      <p className="text-sm text-muted-foreground">
        This is the collection — every disc, and which shelf it is on. A couple of things
        worth setting up, and then you are done.
      </p>
      <p className="text-sm text-muted-foreground">
        {isAdmin
          ? 'You can add, edit and remove discs. Everything you change is recorded.'
          : 'You can browse everything and keep your own watch history.'}
      </p>
    </div>
  )
}

function Catalogue() {
  // The April version read `d?.meta?.total` — the `{data, meta, errors}` envelope that
  // `DECISIONS.md` #6 removed — so it rendered a loading skeleton for ever. Reading the
  // real shape, through the shared schema, is the whole fix.
  const collection = useQuery({
    queryKey: ['movies', 'onboarding-count'],
    queryFn: () => fetchMovies({}, 1, 1),
  })

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Your collection</h2>
      <p className="text-sm text-muted-foreground">
        Already imported and ready to browse. You can add discs one at a time from
        <span className="font-medium text-foreground"> Add a disc</span>.
      </p>
      <div className="flex items-center gap-4 rounded-lg border border-border bg-card p-4">
        <span className="text-3xl">📀</span>
        <div>
          {collection.data ? (
            <p className="text-2xl font-bold text-foreground">
              {collection.data.totalItems.toLocaleString()}
            </p>
          ) : collection.isError ? (
            <p className="text-sm text-destructive">Could not load the count.</p>
          ) : (
            <div className="h-7 w-20 animate-pulse rounded bg-muted" />
          )}
          <p className="text-xs text-muted-foreground">
            discs
            {collection.data
              ? ` across ${collection.data.totalMovies.toLocaleString()} films`
              : ''}
          </p>
        </div>
      </div>
    </div>
  )
}

function InstallApp() {
  const { state, install } = usePwaInstall()
  const [outcome, setOutcome] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Add it to your phone</h2>
      <p className="text-sm text-muted-foreground">
        Installed, it opens full-screen and keeps working when you have no signal — which
        is most of the point, since the discs are on a shelf and the shelf has no wi-fi.
      </p>

      {state === 'installed' ? (
        <p className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 text-sm text-foreground">
          <Check className="h-4 w-4 text-primary" /> Already installed on this device.
        </p>
      ) : state === 'available' ? (
        <>
          <Button
            type="button"
            onClick={() => void install().then((result) => setOutcome(result))}
          >
            Install app
          </Button>
          {outcome === 'dismissed' && (
            <p className="text-xs text-muted-foreground">
              No problem — you can install it later from your browser menu.
            </p>
          )}
        </>
      ) : (
        // iOS Safari never fires `beforeinstallprompt`, so there is no button to offer.
        // Saying how to do it beats a button that does nothing.
        <div className="space-y-2 rounded-lg border border-border bg-card p-4 text-sm">
          <p className="font-medium text-foreground">On iPhone or iPad</p>
          <p className="text-xs text-muted-foreground">
            Tap Share, then <span className="font-medium">Add to Home Screen</span>.
          </p>
          <p className="pt-2 font-medium text-foreground">On a computer</p>
          <p className="text-xs text-muted-foreground">
            Use the install icon in the address bar, if your browser offers one.
          </p>
        </div>
      )}
    </div>
  )
}

function ThemeChoice() {
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Light or dark</h2>
      <p className="text-sm text-muted-foreground">Change it any time from the sidebar.</p>
      <div className="grid grid-cols-2 gap-3">
        {(
          [
            ['dark', Moon, 'Dark'],
            ['light', Sun, 'Light'],
          ] as const
        ).map(([value, Icon, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => {
              if (theme !== value) toggleTheme()
            }}
            aria-pressed={theme === value}
            className={`flex flex-col items-center gap-2 rounded-lg border p-5 transition-colors ${
              theme === value
                ? 'border-primary bg-primary/5 text-foreground'
                : 'border-border text-muted-foreground hover:text-foreground'
            }`}
          >
            <Icon className="h-6 w-6" />
            <span className="text-sm font-medium">{label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

/** Only what exists. Every entry here is a page that is built and reachable today. */
const TOUR = [
  { icon: '🎬', title: 'Movies', body: 'Browse the whole collection, and filter by shelf, decade, rating or whether you have seen it.' },
  { icon: '📍', title: 'Where it is', body: 'Every disc shows its section and shelf, so "which one is Heat on?" has an answer.' },
  { icon: '👁', title: 'Watch log', body: 'Mark a film watched and rate it. Yours is separate from his.' },
]

function Tour() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">What is in here</h2>
      <div className="space-y-2">
        {TOUR.map((item) => (
          <div key={item.title} className="flex gap-3 rounded-lg border border-border bg-card p-4">
            <span className="text-xl">{item.icon}</span>
            <div>
              <p className="text-sm font-semibold text-foreground">{item.title}</p>
              <p className="text-xs text-muted-foreground">{item.body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Done({ isAdmin }: { isAdmin: boolean }) {
  return (
    <div className="space-y-4 text-center">
      <span className="text-5xl">🍿</span>
      <h2 className="text-2xl font-bold text-foreground">That is everything</h2>
      <p className="text-sm text-muted-foreground">
        {isAdmin
          ? 'Add a disc whenever you buy one — it will queue up if you have no signal.'
          : 'Have a look around. Everything is browsable, on or offline.'}
      </p>
    </div>
  )
}

export default function OnboardingPage() {
  const navigate = useNavigate()
  const { profile, refresh } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const [saving, setSaving] = useState(false)

  const steps: StepDef[] = [
    {
      id: 'welcome',
      label: 'Welcome',
      node: <Welcome isAdmin={isAdmin} name={profile?.displayName ?? 'there'} />,
    },
    // The only admin-specific step: a viewer cannot add discs, so the count and the
    // pointer to "Add a disc" are not theirs to act on.
    ...(isAdmin ? [{ id: 'catalogue', label: 'Catalogue', node: <Catalogue /> }] : []),
    { id: 'install', label: 'Install', node: <InstallApp /> },
    // After Install on purpose: on iOS push only works from an installed app, so
    // asking before that step would fail for the one platform that needs the order.
    { id: 'notifications', label: 'Alerts', node: <NotificationsStep /> },
    { id: 'theme', label: 'Theme', node: <ThemeChoice /> },
    { id: 'tour', label: 'Tour', node: <Tour /> },
    { id: 'done', label: 'Done', node: <Done isAdmin={isAdmin} /> },
  ]

  const total = steps.length
  const [step, setStep] = useState(() => {
    // Resumable, per §2.8. `localStorage` because it is a per-device position in a flow,
    // not user data — the same reasoning as `DECISIONS.md` #8.
    const stored = Number(localStorage.getItem(STEP_KEY))
    return Number.isInteger(stored) && stored >= 0 && stored < total ? stored : 0
  })

  useEffect(() => {
    localStorage.setItem(STEP_KEY, String(step))
  }, [step])

  // Someone who has already finished should never see this again, however they arrived.
  useEffect(() => {
    if (profile?.onboardingCompleted) navigate('/movies', { replace: true })
  }, [profile, navigate])

  async function finish() {
    setSaving(true)
    try {
      await completeOnboarding()
      localStorage.removeItem(STEP_KEY)
      // Re-read the profile so the gate in `ProtectedRoute` sees the new state; without
      // it, navigating to /movies bounces straight back here.
      await refresh()
      navigate('/movies', { replace: true })
    } finally {
      setSaving(false)
    }
  }

  const isLast = step === total - 1
  const current = steps[step]

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="w-full max-w-lg">
        <div className="mb-6">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">
              Step {step + 1} of {total} — {current.label}
            </span>
            {/* Skippable, per §2.8: nothing in here has to be done. */}
            {!isLast && (
              <button
                type="button"
                onClick={() => void finish()}
                className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                Skip setup
              </button>
            )}
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${((step + 1) / total) * 100}%` }}
            />
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-6">{current.node}</div>

        <div className="mt-6 flex items-center justify-between gap-3">
          <Button
            type="button"
            variant="ghost"
            disabled={step === 0 || saving}
            onClick={() => setStep((value) => Math.max(0, value - 1))}
          >
            Back
          </Button>
          <Button
            type="button"
            disabled={saving}
            onClick={() => (isLast ? void finish() : setStep((value) => value + 1))}
          >
            {saving && <Loader2 className="h-4 w-4 animate-spin" />}
            {isLast ? 'Start browsing' : 'Next'}
          </Button>
        </div>
      </div>
    </div>
  )
}
