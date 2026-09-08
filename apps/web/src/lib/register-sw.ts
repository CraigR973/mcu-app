/**
 * Register the service worker, and keep it updating.
 *
 * Split out of `main.tsx` so the app's entry point stays readable and so this can be
 * skipped wholesale in tests and in dev, where a worker caching a module graph turns
 * every subsequent edit into a debugging exercise.
 */
export function registerServiceWorker(): void {
  if (import.meta.env.DEV && import.meta.env.VITE_PWA_DEV !== 'true') return
  if (!('serviceWorker' in navigator)) return

  void import('virtual:pwa-register')
    .then(({ registerSW }) => {
      registerSW({
        immediate: true,
        // No prompt. The worker calls `skipWaiting()` on install, so there is nothing
        // to ask about — and asking is what deadlocked `the-coupon` on iOS, where an
        // overlay sat above the refresh banner and the worker showing the overlay was
        // the one that could never be replaced. See `src/sw.ts`.
        onRegisteredSW(_url, registration) {
          // Hourly, and only while the tab is open. Without it a phone left on the home
          // screen for a week keeps serving a week-old bundle.
          if (registration) {
            setInterval(() => void registration.update(), 60 * 60 * 1000)
          }
        },
      })
    })
    .catch(() => {
      // A failed registration must not take the app down with it: everything still
      // works online, which is the state the person is in if this failed.
    })
}
