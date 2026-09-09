/// <reference lib="WebWorker" />
import { CacheableResponsePlugin } from 'workbox-cacheable-response'
import { clientsClaim } from 'workbox-core'
import { ExpirationPlugin } from 'workbox-expiration'
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { CacheFirst, NetworkFirst } from 'workbox-strategies'

// vite-plugin-pwa replaces `self.__WB_MANIFEST` with the precache manifest at build time.
declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null } | string>
}

/**
 * **The iOS deadlock fix.** Activate immediately rather than waiting for the page to be
 * told to refresh.
 *
 * Ported from `the-coupon`, where a service worker registered with `registerType:
 * 'prompt'` sat in `waiting` until the user tapped a banner — and an overlay above that
 * banner on iOS meant they never could. The worker showing the overlay was therefore the
 * one worker that could never be replaced, and only clearing site data broke the cycle.
 *
 * Taking control on install costs a page that may be running slightly older JS than the
 * worker now serving it, which is survivable and self-corrects on the next navigation. A
 * worker that cannot be updated is not survivable.
 */
self.skipWaiting()
clientsClaim()

cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)

/**
 * SPA navigations: try the network, fall back to the cached shell.
 *
 * `denylist` keeps `/api/*` out — those are data, handled below, and serving `index.html`
 * for a failed API call would hand the fetch layer an HTML body to parse as JSON.
 */
registerRoute(
  new NavigationRoute(
    new NetworkFirst({ cacheName: 'mcu-navigation', networkTimeoutSeconds: 3 }),
    { denylist: [/^\/api\//] },
  ),
)

/**
 * Collection reads — §13.8's "turning off network still allows browsing and searching".
 *
 * Network-first with a short timeout, so a working connection always wins and the cache
 * is only ever the fallback. The three-second timeout is what makes a flaky connection
 * feel like an offline one rather than a hang.
 *
 * **This deliberately diverges from `the-coupon`, which drops every API response from the
 * cache** (its `respectNoStore` plugin, for SEC-13). That app's data is other people's;
 * this app's is the owner's own catalogue on the owner's own phone, and the batch's
 * acceptance criterion *is* that it survives the network going away.
 *
 * **That last sentence used to read "the API sets no `Cache-Control`, so nothing here is
 * overriding a stated instruction", and it stopped being true.** Batch 17's `.ics` feed and
 * Batch 27's gift page both answer `Cache-Control: private, no-store`, and this route
 * matched them on pathname alone — so a public gift page a family member opened was being
 * stored for 24 hours in *their* browser against the API's explicit instruction. Caught by
 * Batch 27's security review.
 *
 * The route now honours `no-store` and matches only this app's own origin. Both matter:
 * the first respects what the API asked for, and the second stops a cross-origin response
 * being cached under a rule written for same-origin catalogue reads.
 *
 * Only `GET` is cached. Writes go through the offline queue in `lib/offline-queue.ts`,
 * which is durable in a way a response cache is not.
 */
registerRoute(
  ({ url, request }) =>
    request.method === 'GET' &&
    url.origin === self.location.origin &&
    url.pathname.startsWith('/api/v1/') &&
    // The two capability URLs. Neither is catalogue data, neither is wanted offline, and
    // both say `no-store` — a rule that reads the API's own instruction rather than
    // listing paths would be better, but a service worker cannot see response headers
    // when deciding whether a route *matches*.
    !url.pathname.startsWith('/api/v1/gift/') &&
    !url.pathname.startsWith('/api/v1/calendar.ics'),
  new NetworkFirst({
    cacheName: 'mcu-api',
    networkTimeoutSeconds: 3,
    plugins: [
      // Roughly the whole catalogue at the page sizes the app asks for, plus room for
      // detail and facet reads. A day, because a disc's metadata does not change hourly
      // and a stale poster beats a blank screen.
      new ExpirationPlugin({ maxEntries: 120, maxAgeSeconds: 60 * 60 * 24 }),
      new CacheableResponsePlugin({ statuses: [200] }),
    ],
  }),
)

/**
 * Posters — §13.8's "cache poster images".
 *
 * Cache-first: a TMDB poster at a given path is immutable, so re-fetching it over the
 * network buys nothing and costs the one thing a phone on a shelf is short of. 400
 * entries covers a good browse of a 1,857-film catalogue without letting the cache grow
 * without bound.
 */
registerRoute(
  ({ url }) => url.origin === 'https://image.tmdb.org',
  new CacheFirst({
    cacheName: 'mcu-posters',
    plugins: [
      new ExpirationPlugin({ maxEntries: 400, maxAgeSeconds: 60 * 60 * 24 * 30 }),
      // TMDB serves posters cross-origin without CORS, so responses arrive opaque with
      // status 0. Allowing 0 is what makes them storable at all; the trade is that we
      // cannot inspect them, which for an image is no loss.
      new CacheableResponsePlugin({ statuses: [0, 200] }),
    ],
  }),
)
