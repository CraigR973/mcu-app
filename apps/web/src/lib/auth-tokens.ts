/**
 * Token storage and the authenticated fetch wrapper.
 *
 * Tokens live in `localStorage`. That is reachable by any script running on the page,
 * which is the accepted cost: the alternative — httpOnly cookies — needs CSRF handling
 * the API does not have, and `vercel.json` ships `script-src 'self'` with no inline or
 * external script permitted, so there is no third-party script to steal them.
 */

import { tokenPairSchema } from '@mcu/shared'

import { shouldEndSession } from './session'

const ACCESS_KEY = 'mcu.accessToken'
const REFRESH_KEY = 'mcu.refreshToken'

const apiOrigin = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''
export const API_BASE = `${apiOrigin}/api/v1`

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(ACCESS_KEY)
  } catch {
    return null
  }
}

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY)
  } catch {
    return null
  }
}

export function storeTokens(accessToken: string, refreshToken: string): void {
  try {
    localStorage.setItem(ACCESS_KEY, accessToken)
    localStorage.setItem(REFRESH_KEY, refreshToken)
  } catch {
    /* private browsing — the session simply will not persist a reload */
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  } catch {
    /* nothing to clear */
  }
}

/**
 * What a renewal attempt came to.
 *
 * - `renewed`: fresh tokens are in storage — from this attempt, or from another tab that
 *   rotated them while this one was in flight.
 * - `refused`: the server examined the refresh token and rejected it. The session is over.
 * - `unavailable`: nobody examined it — a 5xx during a deploy, a 429, a gateway. The
 *   session is intact and the tokens are kept (`DECISIONS.md` #48, #200).
 */
type RefreshOutcome =
  | { kind: 'renewed' }
  | { kind: 'refused' }
  | { kind: 'unavailable'; status: number }

/** In-flight refresh, shared so concurrent 401s trigger one rotation rather than many. */
let refreshInFlight: Promise<RefreshOutcome> | null = null

async function refreshTokens(): Promise<RefreshOutcome> {
  const presented = getRefreshToken()
  if (!presented) return { kind: 'refused' }

  const response = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refreshToken: presented }),
  })
  if (!response.ok) {
    // This used to clear the tokens on *any* failure, so a renewal that met a restarting
    // server signed the person out — the rule `AuthProvider` already refuses to break.
    if (!shouldEndSession(response.status)) return { kind: 'unavailable', status: response.status }
    // Tokens rotate on every use. If another tab renewed while this request was in flight,
    // the server refused ours *because* it had just issued its successor — and clearing
    // storage now would throw that successor away and sign out both tabs.
    if (getRefreshToken() !== presented) return { kind: 'renewed' }
    clearTokens()
    return { kind: 'refused' }
  }

  try {
    const body: unknown = await response.json()
    const tokens = tokenPairSchema.parse(body)
    storeTokens(tokens.accessToken, tokens.refreshToken)
    return { kind: 'renewed' }
  } catch {
    // The server rotated — the token we presented is revoked — and we cannot read its
    // replacement, so there is no session left to keep.
    clearTokens()
    return { kind: 'refused' }
  }
}

/** A fresh response per caller: concurrent requests share one refresh, and a body can
 *  only be read once. */
function renewalUnavailable(status: number): Response {
  return new Response(
    JSON.stringify({ detail: 'Your session could not be renewed just now. Try again in a moment.' }),
    { status, headers: { 'Content-Type': 'application/json' } },
  )
}

/**
 * `fetch` with the bearer token attached, retried once through a token refresh.
 *
 * The retry is deliberately single: a second 401 after a successful rotation means the
 * session is genuinely finished, and retrying again would spin.
 */
export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const send = (): Promise<Response> => {
    const token = getAccessToken()
    // **`FormData` must set its own `Content-Type`.** A multipart body needs the boundary
    // the browser generates, and a hand-written `multipart/form-data` header omits it —
    // the request goes out looking fine and the server parses nothing out of it. Batch 25's
    // photo upload is the first body here that is not JSON.
    const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
    return fetch(path.startsWith('http') ? path : `${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...((options.headers as Record<string, string>) ?? {}),
      },
    })
  }

  const response = await send()
  if (response.status !== 401) return response

  refreshInFlight ??= refreshTokens().finally(() => {
    refreshInFlight = null
  })
  const outcome = await refreshInFlight
  if (outcome.kind === 'refused') return response
  // Hand back the renewal's own status, not the original 401: a caller that sees a 401
  // ends the session, and nothing examined these credentials and refused them.
  if (outcome.kind === 'unavailable') return renewalUnavailable(outcome.status)

  return send()
}
