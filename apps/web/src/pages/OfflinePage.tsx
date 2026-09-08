import { WifiOff } from 'lucide-react'
import { Link } from 'react-router-dom'

import { useOnlineStatus } from '@/hooks/useOnlineStatus'

/**
 * Where a navigation lands when the shell is cached but the route is not.
 *
 * Says what still works rather than only that something failed — with the collection
 * cached, "you are offline" is much less true than it sounds, and a page that only
 * apologises would send someone away from an app that would have answered them.
 */
export default function OfflinePage() {
  const isOnline = useOnlineStatus()

  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-4 p-8 text-center">
      <WifiOff className="h-12 w-12 text-muted-foreground/40" />
      <h1 className="text-xl font-bold text-foreground">
        {isOnline ? 'That page isn’t cached' : 'You’re offline'}
      </h1>
      <p className="text-sm text-muted-foreground">
        The collection you have already browsed is still here, and anything you change is
        saved on this device and sent when you’re back.
      </p>
      <Link
        to="/movies"
        className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground"
      >
        Browse the collection
      </Link>
    </div>
  )
}
