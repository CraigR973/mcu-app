import { useState, type FormEvent } from 'react'
import { Eye, EyeOff, KeyRound, Loader2, UserRound, WifiOff } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

import { BrandLockup } from '@/components/brand/BrandLockup'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/context/auth'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'

/**
 * The private front door to the archive.
 */
export default function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const isOnline = useOnlineStatus()
  const from = (location.state as { from?: string })?.from ?? '/'

  const [displayName, setDisplayName] = useState('')
  const [pin, setPin] = useState('')
  const [showPin, setShowPin] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const result = await signIn(displayName.trim(), pin)
      if (result.error) {
        setError(result.error)
        setPin('')
        return
      }
      navigate(from, { replace: true })
    } catch {
      // `signIn` normally converts transport failures to a useful result. Keeping the
      // page defensive means an unexpected rejection still releases the loading state.
      setError('Could not reach the archive. Check your connection and try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="relative min-h-[100dvh] overflow-hidden bg-background">
      <div className="pointer-events-none absolute inset-y-0 left-0 hidden w-px bg-accent/45 lg:left-[calc(50%-1px)] lg:block" />
      <div className="mx-auto grid min-h-[100dvh] w-full max-w-[90rem] lg:grid-cols-2">
        <section className="relative hidden lg:flex lg:min-h-full lg:items-center lg:justify-center lg:border-b-0 lg:border-r lg:border-border lg:overflow-hidden">
          {/* Hero photo backdrop with overlay gradient for text readability on mobile */}
          <img
            src="/brand/hero-photo-five-v3.png"
            alt="Mark's Cinematic Universe"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/50 to-background/20" />
          <div className="relative z-10 max-w-md">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-accent">
              Private film archive
            </p>
            <p className="mt-6 font-display text-xl leading-8 text-foreground">
              Every edition, every shelf, every film night—kept in one carefully
              maintained collection.
            </p>
            <p className="mt-4 text-sm leading-6 text-muted-foreground">
              A private catalogue for Craig and Mark.
            </p>
          </div>
        </section>
        <section className="relative flex min-h-64 flex-col justify-between border-b border-border bg-cover bg-center px-6 py-8 sm:px-10 sm:py-10 lg:hidden" style={{ backgroundImage: 'url(/brand/hero-photo-five-v3.png)' }}>
          <div className="absolute inset-0 bg-gradient-to-b from-background/80 via-background/40 to-background/20" />
          <div className="relative z-10 w-fit">
            <BrandLockup variant="horizontal" width={280} label="Mark's Cinematic Universe" />
            <p className="mt-5 text-[0.6875rem] font-semibold uppercase tracking-[0.24em] text-accent">
              Private film archive
            </p>
          </div>
        </section>

        <section className="flex items-center px-5 py-10 sm:px-10 lg:px-16 lg:py-16">
          <div className="mx-auto w-full max-w-md">
            <div className="mb-8">
              <p className="page-kicker eyebrow-rule">Archive access</p>
              <h1 className="font-display text-4xl font-semibold tracking-[-0.03em] text-foreground">
                Welcome back
              </h1>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Sign in with the name and PIN assigned to you.
              </p>
            </div>

            {!isOnline && (
              <div
                role="status"
                className="mb-5 flex gap-3 rounded-lg border border-warning/35 bg-warning/10 px-4 py-3 text-sm text-foreground"
              >
                <WifiOff className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
                <p>
                  You appear to be offline. Reconnect before signing in; saved archive
                  pages remain available after your session has been confirmed.
                </p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div
                  id="sign-in-error"
                  role="alert"
                  className="rounded-lg border border-destructive/35 bg-destructive/10 px-4 py-3 text-sm leading-6 text-destructive"
                >
                  {error}
                </div>
              )}

              <div>
                <label htmlFor="displayName" className="field-label">
                  Name
                </label>
                <div className="relative">
                  <UserRound
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                    aria-hidden
                  />
                  <Input
                    id="displayName"
                    type="text"
                    autoComplete="username"
                    autoCapitalize="words"
                    autoFocus
                    required
                    value={displayName}
                    onChange={(event) => setDisplayName(event.target.value)}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={error ? 'sign-in-error' : undefined}
                    className="pl-10"
                    placeholder="Your name"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="pin" className="field-label">
                  PIN
                </label>
                <div className="relative">
                  <KeyRound
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                    aria-hidden
                  />
                  <Input
                    id="pin"
                    // `inputMode="numeric"` preserves leading zeroes while showing the
                    // numeric keyboard on a phone.
                    type={showPin ? 'text' : 'password'}
                    inputMode="numeric"
                    pattern="[0-9]*"
                    autoComplete="current-password"
                    required
                    minLength={4}
                    maxLength={8}
                    value={pin}
                    onChange={(event) => setPin(event.target.value.replace(/\D/g, ''))}
                    aria-invalid={error ? true : undefined}
                    aria-describedby={error ? 'sign-in-error pin-hint' : 'pin-hint'}
                    className="pl-10 pr-12 font-mono tracking-[0.25em]"
                    placeholder="••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPin((visible) => !visible)}
                    className="touch-target absolute right-0 top-1/2 flex -translate-y-1/2 items-center justify-center px-3 text-muted-foreground hover:text-foreground"
                    aria-label={showPin ? 'Hide PIN' : 'Show PIN'}
                    aria-pressed={showPin}
                  >
                    {showPin ? (
                      <EyeOff className="h-4 w-4" aria-hidden />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden />
                    )}
                  </button>
                </div>
                <p id="pin-hint" className="field-hint">
                  Your 4–8 digit personal access code.
                </p>
              </div>

              <Button
                type="submit"
                size="lg"
                className="w-full"
                disabled={isSubmitting || !isOnline}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="animate-spin" aria-hidden />
                    Signing in…
                  </>
                ) : (
                  'Enter the archive'
                )}
              </Button>
            </form>

            {/* No sign-up link: there is no sign-up route, by design (#11). */}
            <p className="mt-8 border-t border-border pt-5 text-xs leading-5 text-muted-foreground">
              This collection is private. Accounts are created by the administrator and
              cannot be requested here.
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}
