import { type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/auth'

interface Props {
  children: ReactNode
  role?: 'admin' | 'viewer'
  skipOnboardingCheck?: boolean
}

export default function ProtectedRoute({ children, role, skipOnboardingCheck }: Props) {
  const { session, profile, isLoading } = useAuth()
  const location = useLocation()

  if (import.meta.env.VITE_SKIP_AUTH === 'true') return <>{children}</>

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  }

  if (role && profile?.role !== role) {
    return <Navigate to="/unauthorized" replace />
  }

  if (!skipOnboardingCheck && profile && !profile.onboarding_completed) {
    return <Navigate to="/onboarding" replace />
  }

  return <>{children}</>
}
