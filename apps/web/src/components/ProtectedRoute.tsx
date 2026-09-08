import { type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/auth'

interface Props {
  children: ReactNode
  role?: 'admin' | 'viewer'
}

export default function ProtectedRoute({ children, role }: Props) {
  const { profile, isLoading, isAuthenticated } = useAuth()
  const location = useLocation()

  // Development only. This used to be reachable in any build, which meant a stray
  // VITE_SKIP_AUTH on a deployment would have opened the whole collection — `import
  // .meta.env.DEV` is compiled to `false` in a production build, so the branch is
  // removed by the bundler rather than merely unreached.
  if (import.meta.env.DEV && import.meta.env.VITE_SKIP_AUTH === 'true') return <>{children}</>

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
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
