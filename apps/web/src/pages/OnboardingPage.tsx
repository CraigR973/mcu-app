import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bell, BookOpen, Check, Disc3, Film, Loader2, LogOut, Monitor, Moon, Smartphone, Sun } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { BrandMark } from '@/components/brand/BrandMark'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/context/auth'
import { useTheme } from '@/context/theme'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { usePushSubscription } from '@/hooks/usePushSubscription'
import { usePwaInstall } from '@/hooks/usePwaInstall'
import { completeOnboarding, fetchMovies } from '@/lib/api'

interface StepDef {
  id: string
  label: string
  node: ReactNode
}

/** `visual` replaces the icon medallion where a step earns real brand artwork — only the
 *  welcome step does. Everywhere else the medallion is the right weight. */
function StepIntro({ icon: Icon, visual, eyebrow, title, children }: { icon: typeof Film; visual?: ReactNode; eyebrow: string; title: string; children: ReactNode }) {
  return (
    <div>
      {visual ?? (
        <span className="mb-5 flex h-11 w-11 items-center justify-center rounded-full border border-accent/45 bg-accent/10 text-accent">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
      )}
      <p className="page-kicker">{eyebrow}</p>
      <h2 tabIndex={-1} data-step-heading className="font-display text-3xl font-semibold tracking-[-0.025em] text-foreground">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-6 text-muted-foreground">{children}</div>
    </div>
  )
}

function Welcome({ isAdmin, name }: { isAdmin: boolean; name: string }) {
  // Personalised poster celebrates Mark's collection in authenticated context
  const isRoomy = useMediaQuery('(min-width: 640px)')
  return (
    <StepIntro
      icon={Film}
      visual={
        <div className="mb-6">
          <img
            src={isRoomy ? '/brand/personalised-poster-icon-1024.png' : '/brand/personalised-poster-icon-512.png'}
            alt="Mark's Cinematic Universe"
            className="rounded-lg border border-border"
          />
        </div>
      }
      eyebrow="Welcome to the archive"
      title={`Good to see you, ${name}`}
    >
      <p>Every film, owned copy and shelf location is catalogued here for Craig and Mark.</p>
      <p>{isAdmin ? 'You can maintain the collection, its wanted titles and lending record. Every change is recorded.' : 'You can explore the full archive, plan film nights and keep your own watch history.'}</p>
    </StepIntro>
  )
}

function Catalogue() {
  const collection = useQuery({
    queryKey: ['movies', 'onboarding-count'],
    queryFn: () => fetchMovies({}, 1, 1),
  })
  const waitingOffline = collection.fetchStatus === 'paused' && collection.data === undefined

  return (
    <div className="space-y-6">
      <StepIntro icon={Disc3} eyebrow="Already catalogued" title="Your collection is ready">
        <p>The archive has already been imported. New purchases can be added one disc at a time from <strong className="text-foreground">Add a disc</strong>.</p>
      </StepIntro>
      <div className="border-y border-border py-5" aria-live="polite">
        {collection.data ? (
          <div className="grid grid-cols-2 divide-x divide-border">
            <div className="pr-5"><p className="font-display text-3xl font-semibold text-foreground">{collection.data.totalItems.toLocaleString()}</p><p className="metadata-label mt-1">Collection items</p></div>
            <div className="pl-5"><p className="font-display text-3xl font-semibold text-foreground">{collection.data.totalMovies.toLocaleString()}</p><p className="metadata-label mt-1">Distinct films</p></div>
          </div>
        ) : collection.isError ? (
          <p role="alert" className="text-sm text-destructive">The live catalogue count could not be loaded. Setup can still continue.</p>
        ) : waitingOffline ? (
          <p className="text-sm text-muted-foreground">Reconnect to see the latest catalogue count. Setup can still continue.</p>
        ) : (
          <div className="h-10 w-full animate-pulse rounded-md bg-muted" aria-label="Loading catalogue count" />
        )}
      </div>
    </div>
  )
}

function InstallApp() {
  const { state, install } = usePwaInstall()
  const [outcome, setOutcome] = useState<string | null>(null)

  return (
    <div className="space-y-6">
      <StepIntro icon={Smartphone} eyebrow="Keep it close" title="Add it to your device">
        <p>Installed, the archive opens full-screen and cached pages remain useful when the collection shelves have no signal.</p>
      </StepIntro>
      {state === 'installed' ? (
        <p className="flex items-center gap-2 border-y border-border py-4 text-sm font-semibold text-success"><Check className="h-4 w-4" aria-hidden />Already installed on this device.</p>
      ) : state === 'available' ? (
        <div><Button type="button" onClick={() => void install().then(setOutcome)}>Install app</Button>{outcome === 'dismissed' && <p className="field-hint">No problem—you can install it later from your browser menu.</p>}</div>
      ) : (
        <div className="grid gap-4 border-y border-border py-5 sm:grid-cols-2">
          <div><p className="text-sm font-semibold text-foreground">iPhone or iPad</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Tap Share, then Add to Home Screen.</p></div>
          <div><p className="text-sm font-semibold text-foreground">Computer</p><p className="mt-1 text-xs leading-5 text-muted-foreground">Use the install icon in the address bar if your browser offers one.</p></div>
        </div>
      )}
    </div>
  )
}

function NotificationsStep() {
  const push = usePushSubscription()
  const [label, setLabel] = useState('')

  useEffect(() => setLabel((current) => current || push.suggestedLabel), [push.suggestedLabel])

  return (
    <div className="space-y-6">
      <StepIntro icon={Bell} eyebrow="Optional alerts" title="Know when something changes">
        <p>Price drops, overdue loans and sale seasons can reach this device. Every alert category remains adjustable later.</p>
      </StepIntro>
      {push.state === 'subscribed' && <p className="flex items-center gap-2 border-y border-border py-4 text-sm font-semibold text-success"><Check className="h-4 w-4" aria-hidden />Notifications are on for this device.</p>}
      {push.state === 'unsupported' && <p className="text-sm leading-6 text-muted-foreground">This browser cannot receive notifications. On iPhone, add the app to the Home Screen first.</p>}
      {push.state === 'denied' && <p className="text-sm leading-6 text-muted-foreground">Notifications are blocked in browser settings. The app cannot ask again until that setting changes.</p>}
      {push.state === 'server-not-configured' && <p className="text-sm leading-6 text-muted-foreground">Notifications are not configured on the server. The rest of the archive is unaffected.</p>}
      {push.state === 'available' && (
        <div className="space-y-3">
          <label htmlFor="device-label" className="field-label">Name this device</label>
          <input id="device-label" value={label} onChange={(event) => setLabel(event.target.value)} maxLength={100} placeholder={push.suggestedLabel} className="form-control" />
          <Button type="button" onClick={() => void push.subscribe(label.trim() || push.suggestedLabel)} disabled={push.busy}>{push.busy && <Loader2 className="animate-spin" aria-hidden />}Turn on notifications</Button>
        </div>
      )}
      {push.error && <p role="alert" className="text-sm text-destructive">{push.error}</p>}
      <p className="text-xs text-muted-foreground">This step is always skippable.</p>
    </div>
  )
}

function ThemeChoice() {
  const { theme, setTheme } = useTheme()
  const choices = [
    { value: 'dark' as const, icon: Moon, label: 'Dark', description: 'Screening-room calm' },
    { value: 'light' as const, icon: Sun, label: 'Light', description: 'Programme-paper warmth' },
    { value: 'system' as const, icon: Monitor, label: 'System', description: 'Follow this device' },
  ]

  return (
    <div className="space-y-6">
      <StepIntro icon={Sun} eyebrow="Reading preference" title="Choose the room lighting"><p>Both themes use the same catalogue hierarchy. Change this choice from the sidebar at any time.</p></StepIntro>
      <div className="grid gap-2 sm:grid-cols-3" role="group" aria-label="Colour theme">
        {choices.map(({ value, icon: Icon, label, description }) => (
          <button key={value} type="button" onClick={() => setTheme(value)} aria-pressed={theme === value} className={`flex min-h-28 flex-col items-start justify-between rounded-lg border p-4 text-left transition-colors ${theme === value ? 'border-primary bg-primary/10 text-foreground' : 'border-input text-muted-foreground hover:bg-muted hover:text-foreground'}`}>
            <Icon className="h-5 w-5" aria-hidden /><span><span className="block text-sm font-semibold">{label}</span><span className="mt-0.5 block text-xs">{description}</span></span>
          </button>
        ))}
      </div>
    </div>
  )
}

const TOUR = [
  { title: 'Find an owned film', body: 'Search answers with format, copies and shelf location.', icon: Film },
  { title: 'Browse the archive', body: 'Grid, list and compact views each preserve the full catalogue.', icon: Disc3 },
  { title: 'Plan together', body: 'Build collections, keep a wanted list and run a two-person movie night.', icon: BookOpen },
]

function Tour() {
  return (
    <div className="space-y-6">
      <StepIntro icon={BookOpen} eyebrow="The essentials" title="Three ways into the archive"><p>Start with the job in front of you. The rest stays close without competing for attention.</p></StepIntro>
      <div className="divide-y divide-border border-y border-border">{TOUR.map(({ title, body, icon: Icon }) => <div key={title} className="flex gap-3 py-4"><Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden /><div><p className="text-sm font-semibold text-foreground">{title}</p><p className="mt-1 text-xs leading-5 text-muted-foreground">{body}</p></div></div>)}</div>
    </div>
  )
}

function Done({ isAdmin }: { isAdmin: boolean }) {
  return <StepIntro icon={Film} eyebrow="Ready for the first feature" title="The archive is yours"><p>{isAdmin ? 'Add a disc whenever the collection changes—even an offline edit will wait safely for a connection.' : 'Explore the collection, keep your own watch history and plan the next screening together.'}</p></StepIntro>
}

export default function OnboardingPage() {
  const navigate = useNavigate()
  const { profile, refresh, signOut } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const contentRef = useRef<HTMLDivElement>(null)

  const steps: StepDef[] = [
    { id: 'welcome', label: 'Welcome', node: <Welcome isAdmin={isAdmin} name={profile?.displayName ?? 'there'} /> },
    ...(isAdmin ? [{ id: 'catalogue', label: 'Catalogue', node: <Catalogue /> }] : []),
    { id: 'install', label: 'Install', node: <InstallApp /> },
    { id: 'notifications', label: 'Alerts', node: <NotificationsStep /> },
    { id: 'theme', label: 'Theme', node: <ThemeChoice /> },
    { id: 'tour', label: 'Tour', node: <Tour /> },
    { id: 'done', label: 'Done', node: <Done isAdmin={isAdmin} /> },
  ]
  const total = steps.length
  const stepKey = `mcu:onboarding-step:${profile?.id ?? 'unknown'}`
  const [step, setStep] = useState(() => {
    const legacy = Number(localStorage.getItem('mcu:onboarding-step'))
    return Number.isInteger(legacy) && legacy >= 0 && legacy < total ? legacy : 0
  })

  useEffect(() => localStorage.setItem(stepKey, String(step)), [step, stepKey])
  useEffect(() => {
    contentRef.current?.querySelector<HTMLElement>('[data-step-heading]')?.focus()
  }, [step])
  useEffect(() => {
    if (profile?.onboardingCompleted) navigate('/movies', { replace: true })
  }, [profile, navigate])

  async function finish() {
    setError(null)
    setSaving(true)
    try {
      await completeOnboarding()
      localStorage.removeItem(stepKey)
      localStorage.removeItem('mcu:onboarding-step')
      await refresh()
      navigate('/movies', { replace: true })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Setup could not be completed. Your place has been saved; please try again.')
    } finally {
      setSaving(false)
    }
  }

  const isLast = step === total - 1
  const current = steps[step]
  const progress = Math.round(((step + 1) / total) * 100)

  return (
    <main className="min-h-[100dvh] bg-background px-4 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-[max(1.5rem,env(safe-area-inset-top))] sm:px-6">
      <div className="mx-auto flex min-h-[calc(100dvh-3rem)] w-full max-w-5xl flex-col">
        <header className="flex items-center justify-between border-b border-border pb-4">
          {/* A slim bar, so the compact mark and the short name — the full lockup belongs
              in the welcome card below, where it has a square to sit in. */}
          <div className="flex min-w-0 items-center gap-3">
            <BrandMark size={36} />
            <div className="min-w-0"><p className="truncate font-display text-lg font-semibold text-foreground">The Real MCU</p><p className="text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Private film archive</p></div>
          </div>
          <Button type="button" variant="ghost" size="sm" onClick={() => void signOut()}><LogOut aria-hidden />Sign out</Button>
        </header>

        <div className="grid flex-1 items-center gap-8 py-8 lg:grid-cols-[15rem_minmax(0,1fr)]">
          <aside aria-label="Setup progress" className="self-stretch border-b border-border pb-5 lg:border-b-0 lg:border-r lg:py-8 lg:pr-8">
            <p className="metadata-label">Setup progress</p>
            <p className="mt-2 font-display text-2xl font-semibold text-foreground">{step + 1} <span className="text-muted-foreground">of {total}</span></p>
            <div role="progressbar" aria-label="Onboarding progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress} className="mt-4 h-1 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary transition-[width]" style={{ width: `${progress}%` }} /></div>
            <ol className="mt-5 hidden space-y-2 lg:block">{steps.map((item, index) => <li key={item.id} className={`flex items-center gap-2 text-xs font-semibold ${index === step ? 'text-primary' : index < step ? 'text-foreground' : 'text-muted-foreground'}`}><span className={`h-1.5 w-1.5 rounded-full ${index <= step ? 'bg-primary' : 'bg-border'}`} />{item.label}</li>)}</ol>
          </aside>

          <section className="mx-auto w-full max-w-xl">
            <div ref={contentRef} className="min-h-[25rem] rounded-xl border border-border bg-card p-6 shadow-soft sm:p-8">{current.node}</div>
            {error && <p role="alert" className="mt-4 rounded-lg border border-destructive/35 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
            <div className="mt-5 flex items-center justify-between gap-3">
              <Button type="button" variant="ghost" disabled={step === 0 || saving} onClick={() => setStep((value) => Math.max(0, value - 1))}>Back</Button>
              <div className="flex items-center gap-2">
                {!isLast && <Button type="button" variant="ghost" disabled={saving} onClick={() => void finish()}>Skip setup</Button>}
                <Button type="button" disabled={saving} onClick={() => isLast ? void finish() : setStep((value) => value + 1)}>{saving && <Loader2 className="animate-spin" aria-hidden />}{isLast ? 'Enter the archive' : 'Continue'}</Button>
              </div>
            </div>
          </section>
        </div>
      </div>
    </main>
  )
}
