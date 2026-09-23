// @vitest-environment happy-dom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { authFetch, getAccessToken, getRefreshToken } from './auth-tokens'

/**
 * `DECISIONS.md` #200 — what a renewal does to the session.
 *
 * The server half of #200 is that renewals never worked at all. This half is what the
 * client does when one fails: only a refusal may sign anybody out.
 */

const tokenPair = (access: string, refresh: string) => ({
  accessToken: access,
  refreshToken: refresh,
  tokenType: 'bearer',
  expiresIn: 86_400,
})

const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function isRenewal(input: RequestInfo | URL): boolean {
  return String(input).endsWith('/auth/refresh')
}

function bearerOf(init: RequestInit | undefined): string | undefined {
  return (init?.headers as Record<string, string> | undefined)?.Authorization
}

beforeEach(() => {
  localStorage.setItem('mcu.accessToken', 'old-access')
  localStorage.setItem('mcu.refreshToken', 'old-refresh')
})

afterEach(() => {
  localStorage.clear()
  vi.unstubAllGlobals()
})

describe('authFetch renewal', () => {
  it('renews an expired session and retries with the new access token', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (isRenewal(input)) return json(200, tokenPair('new-access', 'new-refresh'))
      return bearerOf(init) === 'Bearer new-access' ? json(200, { ok: true }) : json(401)
    })
    vi.stubGlobal('fetch', fetchMock)

    const response = await authFetch('/auth/me')

    expect(response.status).toBe(200)
    expect(getAccessToken()).toBe('new-access')
    expect(getRefreshToken()).toBe('new-refresh')
  })

  it('keeps the session when the renewal meets a server that is not answering', async () => {
    // The regression #200 also closes: any failed renewal used to clear the tokens, so a
    // renewal that landed on a restarting container signed the person out.
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => (isRenewal(input) ? json(503) : json(401))))

    const response = await authFetch('/auth/me')

    // Not the original 401 — a caller that sees 401 ends the session.
    expect(response.status).toBe(503)
    expect(getAccessToken()).toBe('old-access')
    expect(getRefreshToken()).toBe('old-refresh')
  })

  it('ends the session when the server refuses the refresh token', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json(401)))

    const response = await authFetch('/auth/me')

    expect(response.status).toBe(401)
    expect(getAccessToken()).toBeNull()
    expect(getRefreshToken()).toBeNull()
  })

  it('keeps the tokens another tab stored while this renewal was in flight', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (isRenewal(input)) {
        // The other tab rotated first, so the server has just revoked the token this tab
        // presented. Its successor must survive the refusal.
        localStorage.setItem('mcu.accessToken', 'other-tab-access')
        localStorage.setItem('mcu.refreshToken', 'other-tab-refresh')
        return json(401)
      }
      return bearerOf(init) === 'Bearer other-tab-access' ? json(200, { ok: true }) : json(401)
    })
    vi.stubGlobal('fetch', fetchMock)

    const response = await authFetch('/auth/me')

    expect(response.status).toBe(200)
    expect(getRefreshToken()).toBe('other-tab-refresh')
  })

  it('gives every concurrent caller a response it can read', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => (isRenewal(input) ? json(502) : json(401)))
    vi.stubGlobal('fetch', fetchMock)

    const [first, second] = await Promise.all([authFetch('/auth/me'), authFetch('/movies')])

    // One renewal for both requests, and neither body was consumed by the other.
    expect(fetchMock.mock.calls.filter(([input]) => isRenewal(input))).toHaveLength(1)
    await expect(first.json()).resolves.toHaveProperty('detail')
    await expect(second.json()).resolves.toHaveProperty('detail')
  })
})
