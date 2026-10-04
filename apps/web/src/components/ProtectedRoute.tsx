import { type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/auth'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/brand/BrandMark'
import { StatePanel } from '@/components/ui/state-panel'

interface Props {
  children: ReactNode
  role?: 'admin' | 'viewer'
}

export default function ProtectedRoute({ children, role }: Props) {
  const { profile, isLoading, isAuthenticated, isSessionUnavailable, refresh } = useAuth()
  const location = useLocation()

  // Development only. This used to be reachable in any build, which meant a stray
  // VITE_SKIP_AUTH on a deployment would have opened the whole collection — `import
  // .meta.env.DEV` is compiled to `false` in a production build, so the branch is
  // removed by the bundler rather than merely unreached.
  if (import.meta.env.DEV && import.meta.env.VITE_SKIP_AUTH === 'true') return <>{children}</>

  if (isLoading) {
    return (
      <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-7 bg-background p-4">
        <BrandMark size={64} label="Mark's Cinematic Universe" />
        <StatePanel tone="loading" title="Opening your archive" description="Confirming this device’s session…" className="w-full max-w-lg" />
      </div>
    )
  }

  if (isSessionUnavailable) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center bg-background p-4">
        <StatePanel
          tone="offline"
          title="Your session could not be confirmed"
          description="You have not been signed out. Reconnect and try again; cached archive pages will remain available once your profile can be restored."
          action={<Button variant="outline" onClick={() => void refresh()}>Try again</Button>}
          className="w-full max-w-lg"
        />
      </div>
    )
  }

  // The query string goes too (Batch T8b): eBay sends a person back to
  // `/settings/ebay/connected` with a one-time code on it, and a sign-in in between must
  // not drop the code, or the person has to start connecting again.
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname + location.search }} replace />
  }

  if (role && profile?.role !== role) {
    return <Navigate to="/unauthorized" replace />
  }

  // The onboarding gate, re-introduced by Batch 9 against a real column. It was removed
  // in Batch 3 because it read a Supabase field that no longer exists, and the wizard it
  // led to had three steps pointing at nothing (`STATUS.md` gotcha 5). Both are fixed:
  // migration `010` owns the flag, and every remaining step does what it says.
  if (profile !== null && !profile.onboardingCompleted && location.pathname !== '/welcome') {
    return <Navigate to="/welcome" replace />
  }

  return <>{children}</>
}
