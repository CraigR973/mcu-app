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

  // The onboarding gate that used to live here belonged to the Supabase profile and
  // redirected into a wizard three of whose nine steps point at nothing (`STATUS.md`
  // gotcha 5). Batch 9 repairs the wizard and owns re-introducing this.
  return <>{children}</>
}
