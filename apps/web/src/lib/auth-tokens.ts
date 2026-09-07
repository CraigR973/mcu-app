/**
 * Token storage and the authenticated fetch wrapper.
 *
 * Tokens live in `localStorage`. That is reachable by any script running on the page,
 * which is the accepted cost: the alternative — httpOnly cookies — needs CSRF handling
 * the API does not have, and `vercel.json` ships `script-src 'self'` with no inline or
 * external script permitted, so there is no third-party script to steal them.
 */

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

/** In-flight refresh, shared so concurrent 401s trigger one rotation rather than many. */
let refreshInFlight: Promise<boolean> | null = null

async function refreshTokens(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false

  const response = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refreshToken }),
  })
  if (!response.ok) {
    clearTokens()
    return false
  }

  const { tokenPairSchema } = await import('@mcu/shared')
  const parsed = tokenPairSchema.safeParse(await response.json())
  if (!parsed.success) {
    clearTokens()
    return false
  }
  storeTokens(parsed.data.accessToken, parsed.data.refreshToken)
  return true
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
    return fetch(path.startsWith('http') ? path : `${API_BASE}${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
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
  const refreshed = await refreshInFlight
  if (!refreshed) return response

  return send()
}
