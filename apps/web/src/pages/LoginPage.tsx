import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/auth'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'

export default function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string })?.from ?? '/'

  const [displayName, setDisplayName] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setIsSubmitting(true)
    const { error } = await signIn(displayName, pin)
    setIsSubmitting(false)
    if (error) {
      setError(error)
      setPin('')
    } else {
      navigate(from, { replace: true })
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center space-y-1">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">Sign in</h1>
          <p className="text-sm text-muted-foreground">Mark&apos;s Cinematic Universe</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div
              role="alert"
              className="rounded-md bg-destructive/15 px-4 py-3 text-sm text-destructive"
            >
              {error}
            </div>
          )}

          <div className="space-y-2">
            <label htmlFor="displayName" className="text-sm font-medium text-foreground">
              Name
            </label>
            <Input
              id="displayName"
              type="text"
              autoComplete="username"
              autoFocus
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Craig"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="pin" className="text-sm font-medium text-foreground">
              PIN
            </label>
            <Input
              id="pin"
              // `inputMode="numeric"` rather than `type="number"`, which would strip a
              // leading zero and turn 0842 into 842.
              type="password"
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete="current-password"
              required
              minLength={4}
              maxLength={8}
              value={pin}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
              placeholder="••••"
            />
          </div>

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        {/* No sign-up link: there is no sign-up route, by design (DECISIONS.md #11). */}
        <p className="text-center text-xs text-muted-foreground">
          This is a private collection. Accounts are not self-serve.
        </p>
      </div>
    </div>
  )
}
