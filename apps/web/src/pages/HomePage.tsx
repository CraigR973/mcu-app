import { Navigate } from 'react-router-dom'

import { BrandMark } from '@/components/brand/BrandMark'
import { useAuth } from '@/context/auth'

export default function HomePage() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-7 bg-background">
        <BrandMark size={64} label="Mark's Cinematic Universe" />
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  // Batch S3, snag 11. `/` used to land on the Archive, and that was the right answer
  // while Home was three-quarters empty — the triage said as much: *"decide 5 first, and
  // 11 falls out of it"*. Now that Home absorbs Stats and Insights and hides what is
  // empty, it is a page worth opening on.
  return <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />
}
