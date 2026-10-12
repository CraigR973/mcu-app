/// <reference lib="WebWorker" />
import { CacheableResponsePlugin } from 'workbox-cacheable-response'
import { clientsClaim } from 'workbox-core'
import { ExpirationPlugin } from 'workbox-expiration'
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { CacheFirst, NetworkFirst } from 'workbox-strategies'

import { opensInApp } from './lib/notification-target'

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

// Drop superseded runtime caches on activate:
//  - `mcu-api`: the pre-partition cache from before the two accounts' caller-specific
//    responses were isolated. Keeping it would let an offline `/auth/me` from one
//    person satisfy the same URL for the other.
//  - `mcu-posters`: entries written while `connect-src` was missing `image.tmdb.org`
//    are cached errors — the SW's fetch was CSP-refused, so `no-response` was stored.
//    A cache-first route would serve those failures for 30 days; the rename to
//    `mcu-posters-v2` abandons them and this delete reclaims the space.
self.addEventListener('activate', (event) => {
  event.waitUntil(Promise.all([caches.delete('mcu-api'), caches.delete('mcu-posters')]))
})

async function apiCacheKey({ request }: { request: Request }): Promise<Request> {
  const authorization = request.headers.get('Authorization')
  if (!authorization) return request

  let identity = authorization
  try {
    const payload = authorization.replace(/^Bearer\s+/i, '').split('.')[1]
    const decoded = atob(payload.replaceAll('-', '+').replaceAll('_', '/'))
    const parsed: unknown = JSON.parse(decoded)
    if (parsed && typeof parsed === 'object' && 'sub' in parsed && typeof parsed.sub === 'string') identity = parsed.sub
  } catch {
    // A non-JWT bearer value is still isolated by its full value below.
  }

  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(identity))
  const partition = Array.from(new Uint8Array(digest).slice(0, 12), (byte) => byte.toString(16).padStart(2, '0')).join('')
  const cacheUrl = new URL(request.url)
  cacheUrl.searchParams.set('__mcu_profile', partition)
  return new Request(cacheUrl.toString(), request)
}

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
 * overriding a stated instruction", and it stopped being true.** Batch 17's `.ics` feed
 * answers `Cache-Control: private, no-store`, and this route once matched it on pathname
 * alone — so a response the API had explicitly asked nobody to store was being kept for 24
 * hours. Caught by Batch 27's security review, which found the same bug on the gift page
 * that Batch S1 has since removed.
 *
 * The route still honours `no-store` and still matches only this app's own origin. Both
 * matter: the first respects what the API asked for, and the second stops a cross-origin
 * response being cached under a rule written for same-origin catalogue reads. **Batch S1
 * removed the gift exclusion because the endpoint is gone, not because the rule relaxed**
 * — every `no-store` route the API still serves is still excluded below.
 *
 * Only `GET` is cached. Writes go through the offline queue in `lib/offline-queue.ts`,
 * which is durable in a way a response cache is not.
 */
registerRoute(
  ({ url, request }) =>
    request.method === 'GET' &&
    url.origin === self.location.origin &&
    url.pathname.startsWith('/api/v1/') &&
    // The capability URL. Not catalogue data, not wanted offline, and it says `no-store`
    // — a rule that reads the API's own instruction rather than listing paths would be
    // better, but a service worker cannot see response headers when deciding whether a
    // route *matches*. Anything new that answers `no-store` belongs on this list.
    !url.pathname.startsWith('/api/v1/calendar.ics'),
  new NetworkFirst({
    cacheName: 'mcu-api-user-v2',
    networkTimeoutSeconds: 3,
    plugins: [
      // Roughly the whole catalogue at the page sizes the app asks for, plus room for
      // detail and facet reads. A day, because a disc's metadata does not change hourly
      // and a stale poster beats a blank screen.
      new ExpirationPlugin({ maxEntries: 120, maxAgeSeconds: 60 * 60 * 24 }),
      new CacheableResponsePlugin({ statuses: [200] }),
      { cacheKeyWillBeUsed: apiCacheKey },
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
    // `-v2`: `mcu-posters` holds `no-response` errors written while the CSP
    // `connect-src` did not allow `image.tmdb.org` and every SW fetch was refused.
    // The rename abandons that poisoned cache; the `activate` handler deletes it.
    cacheName: 'mcu-posters-v2',
    plugins: [
      new ExpirationPlugin({ maxEntries: 400, maxAgeSeconds: 60 * 60 * 24 * 30 }),
      // TMDB serves posters cross-origin without CORS, so responses arrive opaque with
      // status 0. Allowing 0 is what makes them storable at all; the trade is that we
      // cannot inspect them, which for an image is no loss.
      new CacheableResponsePlugin({ statuses: [0, 200] }),
    ],
  }),
)

// ---------------------------------------------------------------------------
// Push (Batch 11) — §6.1, §6.2
// ---------------------------------------------------------------------------

/** What the API encrypts into a push. Mirrors `notification_payload` on the server. */
interface PushPayload {
  title?: string
  body?: string
  url?: string | null
  category?: string
  tag?: string
}

/**
 * Show the notification the API sent.
 *
 * **`event.waitUntil` is not optional here.** A push handler that returns before its
 * `showNotification` promise settles is terminated by the browser, and on some platforms
 * a push that resolves without displaying anything shows a generic "This site has been
 * updated in the background" notice instead — which looks like a bug in the app and is
 * un-debuggable from the outside.
 *
 * The payload is parsed defensively: a malformed body must still produce *a* notification,
 * because the alternative is the browser's own generic one.
 */
self.addEventListener('push', (event) => {
  let payload: PushPayload = {}
  try {
    payload = (event.data?.json() ?? {}) as PushPayload
  } catch {
    payload = { body: event.data?.text() }
  }

  const title = payload.title ?? "Mark's Cinematic Universe"
  event.waitUntil(
    self.registration.showNotification(title, {
      body: payload.body ?? '',
      // There has never been an `/icons/` directory in `public/`, at any point, so every
      // push notification since Batch 11 has 404'd its icon and fallen back to the
      // browser's own glyph. The brand assets live under `/brand/`.
      icon: '/brand/app-icon-concept-art-192.png',
      // A badge is a mask: the platform keeps the alpha channel and throws the colour
      // away, so the detailed emblem shrunk into a 24dp slot resolves to a grey blob.
      // This is the approved one-colour mark, drawn for exactly this.
      badge: '/brand/notification-badge-96.png',
      // `tag` collapses a repeat of the same notification rather than stacking it. The
      // server sends the notification's own id, so two different alerts never collapse
      // into one and a re-delivered one never appears twice.
      tag: payload.tag,
      data: { url: payload.url ?? '/notifications', category: payload.category },
    }),
  )
})

/**
 * Tapping a notification focuses the app rather than opening a second copy of it.
 *
 * `clients.matchAll` first: on a phone the app is usually already open behind the
 * notification shade, and `openWindow` there leaves the person with two instances and an
 * offline queue split across both.
 *
 * **Batch T8a: a link elsewhere opens elsewhere.** A price alert's link is the eBay listing,
 * one tap to Buy (#203). Navigating the app's window there would replace the app, so it
 * opens in a window of its own and the app stays where it was.
 */
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = (event.notification.data as { url?: string } | undefined)?.url ?? '/notifications'

  event.waitUntil(
    (async () => {
      if (!opensInApp(target, self.location.origin)) {
        await self.clients.openWindow(target)
        return
      }
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const client of windows) {
        if (new URL(client.url).origin === self.location.origin) {
          await client.focus()
          // `navigate` needs the client to be controlled; fall back to focusing alone
          // rather than failing the whole handler.
          if ('navigate' in client) {
            await client.navigate(target).catch(() => undefined)
          }
          return
        }
      }
      await self.clients.openWindow(target)
    })(),
  )
})

/**
 * A subscription the browser rotates must be re-registered, or push stops silently.
 *
 * Browsers fire this rarely and without warning — the endpoint is replaced and every
 * future send to the old one answers `410`. The service worker cannot authenticate to the
 * API on its own (the access token lives in the page), so it tells any open page to
 * re-subscribe. Since Batch X3 that is true: the shell's `PushHealthBanner` compares this
 * browser's subscription with the server's devices on every open and on this message, and
 * registers the phone again (`lib/push-health.ts`). Before X3 the page only re-read its
 * own state, and nothing re-registered anything.
 */
self.addEventListener('pushsubscriptionchange', (event) => {
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      for (const client of windows) {
        client.postMessage({ type: 'mcu-push-subscription-changed' })
      }
    })(),
  )
})
