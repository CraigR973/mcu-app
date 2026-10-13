/**
 * Which requests the service worker keeps for offline reading — Batch X8 (UX48-01).
 *
 * The rule used to match only the page's own origin. Production's API is on Railway and the
 * page on Vercel, so in production the worker never kept a single API answer: offline, the
 * app said "You can still browse" above "Failed to fetch". Batch 8 was verified through
 * Vite's proxy, where the two share an origin, which is why nobody saw it. The rule now
 * matches the configured API's origin as well (`VITE_API_URL`, the same value every fetch
 * uses), and is pure so a test can hold it to the cross-origin case.
 */

/** The runtime cache holding API reads, one partition per person (see `sw.ts`). */
export const API_CACHE_NAME = 'mcu-api-user-v2'

/** The origin API calls go to: the configured one, else the page's own (dev and preview). */
export function apiOriginFor(configured: string | undefined, pageOrigin: string): string {
  if (!configured) return pageOrigin
  try {
    return new URL(configured).origin
  } catch {
    return pageOrigin
  }
}

export function isCachedApiRead(
  url: URL,
  method: string,
  pageOrigin: string,
  configuredApi: string | undefined,
): boolean {
  return (
    method === 'GET' &&
    (url.origin === pageOrigin || url.origin === apiOriginFor(configuredApi, pageOrigin)) &&
    url.pathname.startsWith('/api/v1/') &&
    // The capability URL. Not catalogue data, not wanted offline, and it says `no-store`
    // — a rule that reads the API's own instruction rather than listing paths would be
    // better, but a service worker cannot see response headers when deciding whether a
    // route *matches*. Anything new that answers `no-store` belongs on this list.
    !url.pathname.startsWith('/api/v1/calendar.ics')
  )
}

/**
 * Drop every kept API answer — at sign-out, so the next person on this phone starts from
 * nothing of the last one's, whatever the per-person keys would have kept apart.
 */
export async function clearCachedApiReads(): Promise<void> {
  try {
    if (typeof caches !== 'undefined') await caches.delete(API_CACHE_NAME)
  } catch {
    /* no Cache Storage here (a private window); nothing was kept */
  }
}
