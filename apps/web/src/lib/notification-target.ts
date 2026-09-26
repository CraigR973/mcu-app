/**
 * Where a tapped notification goes — Batch T8a.
 *
 * A notification about the app opens in the app, as it always has. One about somewhere else
 * (an eBay listing a price alert found) opens there, in a window of its own. Steering the
 * app's own window to eBay would take the app away, and an installed app on a phone has no
 * address bar to come back with.
 *
 * Kept apart from `sw.ts` so it can be tested: the service worker cannot be.
 */
export function opensInApp(url: string, origin: string): boolean {
  try {
    return new URL(url, origin).origin === origin
  } catch {
    // An address that does not parse is treated as the app's, whose fallback is a page.
    return true
  }
}
