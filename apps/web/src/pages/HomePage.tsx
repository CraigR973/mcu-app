import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/auth'
import { Button } from '../components/ui/button'

export default function HomePage() {
  const { user, profile, signOut } = useAuth()
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">MCU — Mark's Cinematic Universe</h1>
        <div className="flex items-center gap-3">
          {user ? (
            <>
              <span className="text-sm text-muted-foreground">{user.email}</span>
              {profile?.role === 'admin' && (
                <Button variant="outline" size="sm" onClick={() => navigate('/admin')}>
                  Admin
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={signOut}>
                Sign out
              </Button>
            </>
          ) : (
            <>
              <Button variant="ghost" size="sm" onClick={() => navigate('/login')}>
                Sign in
              </Button>
              <Button size="sm" onClick={() => navigate('/signup')}>
                Sign up
              </Button>
            </>
          )}
        </div>
      </header>

      <main className="flex flex-col items-center justify-center py-24 px-4 text-center space-y-4">
        <h2 className="text-4xl font-bold tracking-tight">Your personal film universe</h2>
        <p className="text-muted-foreground max-w-md">
          Track every movie you've watched, rate them, and build your watchlist.
        </p>
        {!user && (
          <Button size="lg" onClick={() => navigate('/signup')}>
            Get started
          </Button>
        )}
      </main>
    </div>
  )
}
