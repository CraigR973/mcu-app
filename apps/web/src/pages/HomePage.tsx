import { Navigate } from 'react-router-dom'

import { useAuth } from '@/context/auth'

export default function HomePage() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-7 bg-background">
        <img src="/brand/personalised-poster-icon-512.png" alt="Mark's Cinematic Universe" className="h-40 w-auto rounded-lg shadow-md" />
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  return <Navigate to={isAuthenticated ? '/movies' : '/login'} replace />
}
