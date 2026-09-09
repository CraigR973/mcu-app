import { Navigate } from 'react-router-dom'

/**
 * The "Watchlist" stub is gone; §3.5's list is called **Wanted** and lives at `/wanted`.
 *
 * A redirect rather than a deletion, because `/watchlist` was in the sidebar since Batch 1
 * and may be bookmarked or cached by the service worker. Batch 9's lesson applies in
 * reverse: a route that renders "coming soon" for ever is the same defect as a button that
 * does nothing, and this one finally has something behind it.
 */
export default function WatchlistPage() {
  return <Navigate to="/wanted" replace />
}
