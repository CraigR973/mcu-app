import { describe, expect, it } from 'vitest'

import { apiOriginFor, isCachedApiRead } from './api-cache-route'

/**
 * **The guard for UX48-01 (CI).** Production's page is on Vercel and its API on Railway; the
 * old rule matched the page's origin only, so the worker never kept an API answer there.
 */
const page = 'https://mcu-app-fawn.vercel.app'
const api = 'https://api-production-a8fe.up.railway.app'
const read = (href: string, method = 'GET', configured: string | undefined = api) =>
  isCachedApiRead(new URL(href), method, page, configured)

describe('the worker keeps API reads', () => {
  it('from the configured API on another origin', () => {
    expect(read(`${api}/api/v1/movies/123`)).toBe(true)
  })

  it('from the page origin, as dev and preview proxy it', () => {
    expect(read(`${page}/api/v1/movies/123`, 'GET', undefined)).toBe(true)
  })

  it('and from no other site', () => {
    expect(read('https://other-app.up.railway.app/api/v1/movies')).toBe(false)
  })

  it('but never a write, the calendar feed, or a path outside the API', () => {
    expect(read(`${api}/api/v1/movies`, 'POST')).toBe(false)
    expect(read(`${api}/api/v1/calendar.ics?token=x`)).toBe(false)
    expect(read(`${api}/health`)).toBe(false)
  })

  it('reads the origin from the configured base, path and all', () => {
    expect(apiOriginFor(`${api}/`, page)).toBe(api)
    expect(apiOriginFor('not a url', page)).toBe(page)
  })
})
