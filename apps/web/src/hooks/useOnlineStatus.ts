import { useEffect, useState } from 'react'

/**
 * Whether the browser believes it has a connection.
 *
 * `navigator.onLine` is a weak signal — it means "an interface is up", not "the API is
 * reachable" — so it is used only to *decide when to try*, never to report success. The
 * queue's own states are what say whether a write actually landed.
 */
export function useOnlineStatus(): boolean {
  const [isOnline, setIsOnline] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine,
  )

  useEffect(() => {
    const goOnline = () => setIsOnline(true)
    const goOffline = () => setIsOnline(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [])

  return isOnline
}
