import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/context/auth'
import { useTheme } from '@/context/theme'

const STEP_KEY = 'mcu:onboarding-step'
const TOTAL_STEPS = 8

function readStep(): number {
  const v = localStorage.getItem(STEP_KEY)
  const n = parseInt(v ?? '0', 10)
  return isNaN(n) || n < 0 || n >= TOTAL_STEPS ? 0 : n
}

// ── Step shells ──────────────────────────────────────────────────────────────

function StepWelcome() {
  return (
    <div className="space-y-4 text-center">
      <div className="text-6xl">🎬</div>
      <h2 className="text-2xl font-bold text-foreground">Welcome to The Real MCU</h2>
      <p className="text-muted-foreground max-w-sm mx-auto">
        Mark's Cinematic Universe — your personal physical-media library. Track every disc,
        build your watchlist, and never lose a film again.
      </p>
    </div>
  )
}

function StepImport() {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Import your collection</h2>
      <p className="text-muted-foreground">
        Already have a catalogue? Import it now or add films one by one later — your choice.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 mt-2">
        <div className="rounded-lg border border-border bg-card p-4 space-y-1">
          <p className="font-semibold text-foreground text-sm">CSV / spreadsheet</p>
          <p className="text-xs text-muted-foreground">Upload a .csv file with your existing data.</p>
          <p className="text-xs text-muted-foreground italic">Coming soon — skip for now.</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 space-y-1">
          <p className="font-semibold text-foreground text-sm">Add manually</p>
          <p className="text-xs text-muted-foreground">Search and add films from your library anytime via the Movies page.</p>
        </div>
      </div>
    </div>
  )
}

function StepEmailConnect({ email }: { email: string | undefined }) {
  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Your email</h2>
      <p className="text-muted-foreground">
        Deal alerts and loan reminders will be sent here. You can manage notification
        preferences in the next step.
      </p>
      <div className="rounded-lg border border-border bg-card px-4 py-3 flex items-center gap-3">
        <span className="text-lg">✉️</span>
        <span className="text-foreground font-medium">{email ?? '—'}</span>
      </div>
      <p className="text-xs text-muted-foreground">
        To change your email, update it in your account settings after setup.
      </p>
    </div>
  )
}

function StepInstallPWA() {
  const [prompted, setPrompted] = useState(false)

  function handleInstall() {
    setPrompted(true)
    // Trigger browser PWA install prompt if available (stored by beforeinstallprompt)
    const ev = (window as unknown as { __pwaInstallPrompt?: { prompt: () => void } }).__pwaInstallPrompt
    if (ev) {
      ev.prompt()
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Install as an app</h2>
      <p className="text-muted-foreground">
        Add The Real MCU to your home screen for quick access — no browser chrome, full-screen experience.
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

function StepNotifications({ prefs, onChange }: { prefs: NotifPrefs; onChange: (p: NotifPrefs) => void }) {
  function toggle(key: keyof NotifPrefs) {
    onChange({ ...prefs, [key]: !prefs[key] })
  }

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold text-foreground">Notifications</h2>
      <p className="text-muted-foreground text-sm">Choose what you'd like to hear about. You can adjust these any time.</p>
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
      <p className="text-muted-foreground text-sm">Pick what looks best to you. Toggle any time from the sidebar.</p>
      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => theme !== 'dark' && toggleTheme()}
          className={`rounded-lg border-2 p-4 flex flex-col items-center gap-2 transition-colors ${
            theme === 'dark'
              ? 'border-primary bg-primary/10'
              : 'border-border bg-card hover:bg-accent/10'
          }`}
        >
          <span className="text-2xl">🌙</span>
          <span className="text-sm font-medium text-foreground">Dark</span>
          {theme === 'dark' && <span className="text-xs text-primary">Selected</span>}
        </button>
        <button
          onClick={() => theme !== 'light' && toggleTheme()}
          className={`rounded-lg border-2 p-4 flex flex-col items-center gap-2 transition-colors ${
            theme === 'light'
              ? 'border-primary bg-primary/10'
              : 'border-border bg-card hover:bg-accent/10'
          }`}
        >
          <span className="text-2xl">☀️</span>
          <span className="text-sm font-medium text-foreground">Light</span>
          {theme === 'light' && <span className="text-xs text-primary">Selected</span>}
        </button>
      </div>
    </div>
  )
}

const TOUR_ITEMS = [
  {
    icon: '🎬',
    title: 'Movies',
    desc: 'Browse and filter your full physical-media library. Grid, list, or compact view — your call.',
  },
  {
    icon: '⭐',
    title: 'Watchlist',
    desc: 'Queue up what you want to watch next. One click to move it to your collection.',
  },
  {
    icon: '📊',
    title: 'Dashboard',
    desc: 'Stats at a glance — total discs, formats breakdown, recent purchases, and more.',
  },
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

function StepDone() {
  return (
    <div className="space-y-4 text-center">
      <div className="text-6xl">🍿</div>
      <h2 className="text-2xl font-bold text-foreground">You're all set!</h2>
      <p className="text-muted-foreground max-w-sm mx-auto">
        Your library awaits. Start browsing, add your first disc, or explore the dashboard.
      </p>
    </div>
  )
}

// ── Step metadata ─────────────────────────────────────────────────────────────

const STEP_TITLES = [
  'Welcome',
  'Import',
  'Email',
  'Install',
  'Notifications',
  'Theme',
  'Tour',
  'Done',
]

// ── Main wizard ───────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const { user, profile, completeOnboarding } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState(readStep)
  const [saving, setSaving] = useState(false)
  const [notifPrefs, setNotifPrefs] = useState<NotifPrefs>({
    price_drops: true,
    deals: true,
    new_releases: true,
    loan_reminders: true,
    purchase_candidates: false,
    on_this_day: true,
  })

  // If already completed, skip to app
  useEffect(() => {
    if (profile?.onboarding_completed) {
      navigate('/movies', { replace: true })
    }
  }, [profile, navigate])

  // Persist step to localStorage for resumability
  useEffect(() => {
    localStorage.setItem(STEP_KEY, String(step))
  }, [step])

  function advance() {
    if (step < TOTAL_STEPS - 1) {
      setStep((s) => s + 1)
    }
  }

  function skip() {
    if (step < TOTAL_STEPS - 1) {
      setStep((s) => s + 1)
    }
  }

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

  const isLastStep = step === TOTAL_STEPS - 1

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Progress bar */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-muted-foreground">
              Step {step + 1} of {TOTAL_STEPS} — {STEP_TITLES[step]}
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
              style={{ width: `${((step + 1) / TOTAL_STEPS) * 100}%` }}
            />
          </div>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-border bg-card shadow-lg p-6 sm:p-8">
          {step === 0 && <StepWelcome />}
          {step === 1 && <StepImport />}
          {step === 2 && <StepEmailConnect email={user?.email} />}
          {step === 3 && <StepInstallPWA />}
          {step === 4 && <StepNotifications prefs={notifPrefs} onChange={setNotifPrefs} />}
          {step === 5 && <StepTheme />}
          {step === 6 && <StepTour />}
          {step === 7 && <StepDone />}

          {/* Actions */}
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
                {saving ? 'Saving…' : 'Go to my library →'}
              </button>
            )}
          </div>
        </div>

        {/* Step dots */}
        <div className="flex justify-center gap-1.5 mt-4">
          {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === step
                  ? 'w-4 bg-primary'
                  : i < step
                  ? 'w-1.5 bg-primary/50'
                  : 'w-1.5 bg-border'
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
