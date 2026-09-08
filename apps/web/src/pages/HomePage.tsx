import { Navigate } from 'react-router-dom'

import { useAuth } from '@/context/auth'

export default function HomePage() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return <Navigate to={isAuthenticated ? '/movies' : '/login'} replace />
}
