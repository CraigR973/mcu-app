import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

/**
 * The browser-page CSP lives in `vercel.json` (the API sets its own, stricter policy in
 * `apps/api/src/middleware.py`). It is checked in, so this suite guards it.
 *
 * The regression this exists for: TMDB image origins were listed under `img-src` but not
 * `connect-src`. That is invisible until the service worker registers — once `sw.ts`'s
 * cache-first poster route intercepts an `<img>` load it re-issues the request as a
 * `fetch()`, which is governed by `connect-src`, not `img-src`. Every poster, backdrop,
 * cast photo and provider logo then failed with a CSP violation in production only.
 */
const vercelConfig = JSON.parse(
  readFileSync(fileURLToPath(new URL('../../../vercel.json', import.meta.url)), 'utf8'),
) as {
  headers: { source: string; headers: { key: string; value: string }[] }[]
}

function cspDirectives(): Map<string, string[]> {
  const header = vercelConfig.headers
    .flatMap((entry) => entry.headers)
    .find((h) => h.key.toLowerCase() === 'content-security-policy')
  if (!header) throw new Error('vercel.json declares no Content-Security-Policy header')

  const directives = new Map<string, string[]>()
  for (const clause of header.value.split(';')) {
    const [name, ...sources] = clause.trim().split(/\s+/)
    if (name) directives.set(name.toLowerCase(), sources)
  }
  return directives
}

describe('vercel.json Content-Security-Policy', () => {
  const csp = cspDirectives()

  it('allows TMDB images under both img-src and connect-src', () => {
    // Both, because a same-origin service worker fetch for an <img> is a connect-src
    // operation. img-src alone lets the picture load only until the SW takes over.
    expect(csp.get('img-src')).toContain('https://image.tmdb.org')
    expect(csp.get('connect-src')).toContain('https://image.tmdb.org')
  })

  it('names the one API host, and no other Railway app', () => {
    // Batch X8 (DS44-07): `*.up.railway.app` let a script post to any Railway app after an
    // injection. The host is production's `VITE_API_URL`; a new API host must be named here
    // and on Vercel together, or every API call is refused.
    expect(csp.get('connect-src')).toContain('https://api-production-a8fe.up.railway.app')
    expect(csp.get('connect-src')?.some((source) => source.includes('*'))).toBe(false)
  })

  it('drops Supabase, which the app left (#17), and Sentry, which is off', () => {
    // Sentry goes back with its DSN: `connect-src` must then name its ingest host.
    for (const directive of ['connect-src', 'img-src']) {
      expect(csp.get(directive)?.join(' ')).not.toMatch(/supabase|sentry/)
    }
  })

  it('pins base-uri and object-src shut', () => {
    expect(csp.get('base-uri')).toEqual(["'self'"])
    expect(csp.get('object-src')).toEqual(["'none'"])
  })
})
