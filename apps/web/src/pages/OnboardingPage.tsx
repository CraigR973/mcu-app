import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/auth'
import { useTheme } from '@/context/theme'

const STEP_KEY = 'mcu:onboarding-step'

function readStep(total: number): number {
  const v = localStorage.getItem(STEP_KEY)
  const n = parseInt(v ?? '0', 10)
  return isNaN(n) || n < 0 || n >= total ? 0 : n
}

// ── Viewer steps (3) ──────────────────────────────────────────────────────────

function StepViewerWelcome() {
  return (
    <div className="space-y-4 text-center">
      <div className="text-6xl">🎬</div>
      <h2 className="text-2xl font-bold text-foreground">Welcome to The Real MCU</h2>
      <p className="text-muted-foreground max-w-sm mx-auto">
        Browse Mark's physical-media library — every disc he owns, searchable and filterable.
        Add films to your watchlist and see what's available to borrow.
      </p>
      <div className="grid grid-cols-3 gap-3 pt-2 text-center">
        {[
          { icon: '🔍', label: 'Browse' },
          { icon: '⭐', label: 'Watchlist' },
          { icon: '📀', label: 'Collection' },
        ].map(({ icon, label }) => (
          <div key={label} className="rounded-lg border border-border bg-card p-3">
            <div className="text-2xl">{icon}</div>
            <p className="text-xs font-medium text-foreground mt-1">{label}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Admin steps (7) ───────────────────────────────────────────────────────────

function StepAdminWelcome() {
  return (
    <div className="space-y-4 text-center">
      <div className="text-6xl">🎬</div>
      <h2 className="text-2xl font-bold text-foreground">Welcome to The Real MCU</h2>
      <p className="text-muted-foreground max-w-sm mx-auto">
        Mark's Cinematic Universe — your personal physical-media library. Track every disc,
        manage your collection, and share it with the world.
      </p>
    </div>
  )
}

function StepCatalog() {
  const [total, setTotal] = useState<number | null>(null)

  useEffect(() => {
    fetch('/api/v1/movies?per_page=1')
      .then((r) => r.json())
      .then((d) => setTotal(d?.meta?.total ?? null))
      .catch(() => null)
  }, [])

  const today = new Date().toLocaleDateString('en-AU', {
    day: 'numeric', month: 'long', year: 'numeric',
  })

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Your collection</h2>
      <p className="text-muted-foreground text-sm">
        Your catalogue is already loaded. You can re-upload your spreadsheet or add individual
        films at any time.
      </p>

      <div className="rounded-lg border border-border bg-card p-4 flex items-center gap-4">
        <span className="text-3xl">📀</span>
        <div>
          {total !== null ? (
            <p className="text-2xl font-bold text-foreground">{total.toLocaleString()}</p>
          ) : (
            <div className="h-7 w-16 rounded bg-muted animate-pulse" />
          )}
          <p className="text-xs text-muted-foreground">
            titles in your library · last updated {today}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4 space-y-1">
          <p className="font-semibold text-foreground text-sm">Re-upload spreadsheet</p>
          <p className="text-xs text-muted-foreground">Replace the catalogue with a new CSV export.</p>
          <p className="text-xs text-muted-foreground italic">Coming soon — available from Admin.</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 space-y-1">
          <p className="font-semibold text-foreground text-sm">Add individually</p>
          <p className="text-xs text-muted-foreground">Search and add films one at a time from the Movies page.</p>
        </div>
      </div>
    </div>
  )
}

function StepEmailConnect({ email }: { email: string | undefined }) {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Your email</h2>
      <p className="text-muted-foreground text-sm">
        Deal alerts and loan reminders will be sent here. Manage preferences in the next step.
      </p>
      <div className="rounded-lg border border-border bg-card px-4 py-3 flex items-center gap-3">
        <span className="text-lg">✉️</span>
        <span className="text-foreground font-medium">{email ?? '—'}</span>
      </div>
      <p className="text-xs text-muted-foreground">
        Change your email via account settings after setup.
      </p>
    </div>
  )
}

function StepInstallPWA() {
  const [prompted, setPrompted] = useState(false)

  function handleInstall() {
    setPrompted(true)
    const ev = (window as unknown as { __pwaInstallPrompt?: { prompt: () => void } }).__pwaInstallPrompt
    if (ev) ev.prompt()
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Install as an app</h2>
      <p className="text-muted-foreground text-sm">
        Add The Real MCU to your home screen for quick, full-screen access.
      </p>
      <div className="rounded-lg border border-border bg-card p-4 space-y-3">
        <div className="flex items-start gap-3">
          <span className="text-lg mt-0.5">📱</span>
          <div>
            <p className="text-sm font-semibold text-foreground">iOS / Safari</p>
            <p className="text-xs text-muted-foreground">Tap Share → "Add to Home Screen"</p>
          </div>
        </div>
        <div className="flex items-start gap-3">
          <span className="text-lg mt-0.5">💻</span>
          <div>
            <p className="text-sm font-semibold text-foreground">Chrome / Edge</p>
            <p className="text-xs text-muted-foreground">Click the install icon in the address bar, or use the button below.</p>
          </div>
        </div>
      </div>
      <button
        onClick={handleInstall}
        disabled={prompted}
        className="w-full rounded-md bg-primary text-primary-foreground py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
      >
        {prompted ? 'Install prompt sent ✓' : 'Install app'}
      </button>
    </div>
  )
}

interface NotifPrefs {
  price_drops: boolean
  deals: boolean
  new_releases: boolean
  loan_reminders: boolean
  purchase_candidates: boolean
  on_this_day: boolean
}

const NOTIF_LABELS: { key: keyof NotifPrefs; label: string; desc: string }[] = [
  { key: 'price_drops', label: 'Price drops', desc: 'Alert when a disc you want goes on sale.' },
  { key: 'deals', label: 'Deals', desc: 'Curated daily deals on physical media.' },
  { key: 'new_releases', label: 'New releases', desc: 'Disc releases for films in your watchlist.' },
  { key: 'loan_reminders', label: 'Loan reminders', desc: 'Remind you to get your discs back.' },
  { key: 'purchase_candidates', label: 'Purchase suggestions', desc: 'Films you might want to add.' },
  { key: 'on_this_day', label: 'On this day', desc: 'Fun facts about films on their anniversaries.' },
]

function StepNotifications({
  prefs, onChange,
}: { prefs: NotifPrefs; onChange: (p: NotifPrefs) => void }) {
  function toggle(key: keyof NotifPrefs) {
    onChange({ ...prefs, [key]: !prefs[key] })
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Notifications</h2>
      <p className="text-muted-foreground text-sm">Choose what you'd like to hear about. Adjust any time.</p>
      <div className="space-y-2">
        {NOTIF_LABELS.map(({ key, label, desc }) => (
          <label
            key={key}
            className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 cursor-pointer hover:bg-accent/10 transition-colors"
          >
            <input
              type="checkbox"
              checked={prefs[key]}
              onChange={() => toggle(key)}
              className="h-4 w-4 accent-primary"
            />
            <div>
              <p className="text-sm font-medium text-foreground">{label}</p>
              <p className="text-xs text-muted-foreground">{desc}</p>
            </div>
          </label>
        ))}
      </div>
    </div>
  )
}

function StepTheme() {
  const { theme, toggleTheme } = useTheme()

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Choose your theme</h2>
      <p className="text-muted-foreground text-sm">Toggle any time from the sidebar.</p>
      <div className="grid grid-cols-2 gap-3">
        {([['dark', '🌙'], ['light', '☀️']] as const).map(([t, icon]) => (
          <button
            key={t}
            onClick={() => theme !== t && toggleTheme()}
            className={`rounded-lg border-2 p-4 flex flex-col items-center gap-2 transition-colors ${
              theme === t ? 'border-primary bg-primary/10' : 'border-border bg-card hover:bg-accent/10'
            }`}
          >
            <span className="text-2xl">{icon}</span>
            <span className="text-sm font-medium text-foreground capitalize">{t}</span>
            {theme === t && <span className="text-xs text-primary">Selected</span>}
          </button>
        ))}
      </div>
    </div>
  )
}

const TOUR_ITEMS = [
  { icon: '🎬', title: 'Movies', desc: 'Browse and filter the full physical-media library. Grid, list, or compact view.' },
  { icon: '⭐', title: 'Watchlist', desc: 'Queue up what you want to watch next.' },
  { icon: '📊', title: 'Dashboard', desc: 'Stats at a glance — total discs, formats, recent purchases.' },
]

function StepTour() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Quick tour</h2>
      <p className="text-muted-foreground text-sm">Here's what you can do with The Real MCU.</p>
      <div className="space-y-3">
        {TOUR_ITEMS.map((item) => (
          <div key={item.title} className="rounded-lg border border-border bg-card p-4 flex gap-3">
            <span className="text-2xl shrink-0">{item.icon}</span>
            <div>
              <p className="font-semibold text-foreground text-sm">{item.title}</p>
              <p className="text-xs text-muted-foreground">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function StepDone({ isAdmin }: { isAdmin: boolean }) {
  return (
    <div className="space-y-4 text-center">
      <div className="text-6xl">🍿</div>
      <h2 className="text-2xl font-bold text-foreground">You're all set!</h2>
      <p className="text-muted-foreground max-w-sm mx-auto">
        {isAdmin
          ? 'Your library awaits. Browse, manage your collection, or explore the admin tools.'
          : 'Dive in. Browse the collection, build a watchlist, or see what Mark recommends.'}
      </p>
    </div>
  )
}

// ── Step definitions ──────────────────────────────────────────────────────────

type StepDef = { id: string; label: string; node: React.ReactNode }

// ── Main wizard ───────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const { user, profile, completeOnboarding } = useAuth()
  const navigate = useNavigate()
  const isAdmin = profile?.role === 'admin'

  const [notifPrefs, setNotifPrefs] = useState<NotifPrefs>({
    price_drops: true,
    deals: true,
    new_releases: true,
    loan_reminders: true,
    purchase_candidates: false,
    on_this_day: true,
  })

  const steps: StepDef[] = isAdmin
    ? [
        { id: 'welcome',       label: 'Welcome',       node: <StepAdminWelcome /> },
        { id: 'catalog',       label: 'Catalogue',     node: <StepCatalog /> },
        { id: 'email',         label: 'Email',         node: <StepEmailConnect email={user?.email} /> },
        { id: 'install',       label: 'Install',       node: <StepInstallPWA /> },
        { id: 'notifications', label: 'Notifications', node: <StepNotifications prefs={notifPrefs} onChange={setNotifPrefs} /> },
        { id: 'theme',         label: 'Theme',         node: <StepTheme /> },
        { id: 'tour',          label: 'Tour',          node: <StepTour /> },
        { id: 'done',          label: 'Done',          node: <StepDone isAdmin /> },
      ]
    : [
        { id: 'welcome', label: 'Welcome', node: <StepViewerWelcome /> },
        { id: 'theme',   label: 'Theme',   node: <StepTheme /> },
        { id: 'done',    label: 'Done',    node: <StepDone isAdmin={false} /> },
      ]

  const total = steps.length
  const [step, setStep] = useState(() => readStep(total))
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (profile?.onboarding_completed) navigate('/movies', { replace: true })
  }, [profile, navigate])

  useEffect(() => {
    localStorage.setItem(STEP_KEY, String(step))
  }, [step])

  const isLastStep = step === total - 1

  function advance() { if (step < total - 1) setStep((s) => s + 1) }
  function skip()    { if (step < total - 1) setStep((s) => s + 1) }

  async function finish() {
    setSaving(true)
    try {
      await completeOnboarding()
      localStorage.removeItem(STEP_KEY)
      navigate('/movies', { replace: true })
    } finally {
      setSaving(false)
    }
  }

  const currentStep = steps[step]

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-muted-foreground">
              Step {step + 1} of {total} — {currentStep.label}
            </span>
            {!isLastStep && (
              <button
                onClick={skip}
                className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2 transition-colors"
              >
                Skip
              </button>
            )}
          </div>
          <div className="h-1.5 w-full rounded-full bg-border overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-300"
              style={{ width: `${((step + 1) / total) * 100}%` }}
            />
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-border bg-card shadow-lg p-6 sm:p-8">
          {currentStep.node}

          <div className="mt-6 flex gap-3">
            {!isLastStep ? (
              <button
                onClick={advance}
                className="flex-1 rounded-md bg-primary text-primary-foreground py-2.5 text-sm font-semibold hover:bg-primary/90 transition-colors"
              >
                Next →
              </button>
            ) : (
              <button
                onClick={finish}
                disabled={saving}
                className="flex-1 rounded-md bg-primary text-primary-foreground py-2.5 text-sm font-semibold hover:bg-primary/90 disabled:opacity-60 transition-colors"
              >
                {saving ? 'Saving…' : 'Go to the library →'}
              </button>
            )}
          </div>
        </div>

        {/* Step dots */}
        <div className="flex justify-center gap-1.5 mt-4">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === step ? 'w-4 bg-primary' : i < step ? 'w-1.5 bg-primary/50' : 'w-1.5 bg-border'
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
