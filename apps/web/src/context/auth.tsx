import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import {
  apiErrorSchema,
  profileResponseSchema,
  tokenPairSchema,
  type ProfileResponse,
} from '@mcu/shared'

import {
  API_BASE,
  authFetch,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  storeTokens,
} from '../lib/auth-tokens'
import { clearQueue } from '../lib/offline-queue'
import { shouldEndSession } from '../lib/session'

interface AuthContextValue {
  profile: ProfileResponse | null
  isLoading: boolean
  isAuthenticated: boolean
  signIn: (displayName: string, pin: string) => Promise<{ error: string | null }>
  signOut: () => Promise<void>
  setPin: (newPin: string, currentPin?: string) => Promise<{ error: string | null }>
}

const AuthContext = createContext<AuthContextValue | null>(null)

/** Pull a human-readable message out of whatever shape the API refused with. */
async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body: unknown = await response.json()
    const parsed = apiErrorSchema.parse(body)
    // A durably rate-limited login answers `{ error: "Rate limit exceeded: ..." }`,
    // not `{ detail: ... }` — reading only `detail` would turn a 429 into "your
    // details are wrong" and invite the retry the limit just refused.
    return parsed.error ?? parsed.detail ?? fallback
  } catch {
    return fallback
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<ProfileResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadProfile = useCallback(async () => {
    if (!getAccessToken() && !getRefreshToken()) {
      setProfile(null)
      setIsLoading(false)
      return
    }
    try {
      const response = await authFetch('/auth/me')
      if (!response.ok) {
        // **Only a rejection ends the session.** A 401 or 403 means the credentials were
        // examined and refused; anything else — a 503 from a restarting container, a
        // gateway, a captive portal — means nobody looked at them.
        //
        // This used to clear the tokens for *any* non-ok response, so the first time the
        // app was opened without signal it signed the person out and destroyed the
        // session that the offline queue was made under. An app whose whole point is to
        // work on a phone in a garage cannot log you out for being in the garage
        // (`DECISIONS.md` #48).
        if (shouldEndSession(response.status)) clearTokens()
        setProfile(null)
        return
      }
      const body: unknown = await response.json()
      setProfile(profileResponseSchema.parse(body))
    } catch {
      // Network failure. The session is intact; we simply cannot confirm it right now.
      setProfile(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadProfile()
  }, [loadProfile])

  const signIn = useCallback(
    async (displayName: string, pin: string): Promise<{ error: string | null }> => {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ displayName, pin }),
      })
      if (!response.ok) {
        return { error: await errorMessage(response, 'Sign in failed') }
      }
      try {
        const body: unknown = await response.json()
        const tokens = tokenPairSchema.parse(body)
        storeTokens(tokens.accessToken, tokens.refreshToken)
      } catch {
        return { error: 'Unexpected response from the server' }
      }
      await loadProfile()
      return { error: null }
    },
    [loadProfile],
  )

  const signOut = useCallback(async () => {
    const refreshToken = getRefreshToken()
    if (refreshToken) {
      // Best effort: the local session ends either way, but telling the API lets it
      // revoke the row so a copied refresh token cannot outlive the sign-out.
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refreshToken }),
        })
      } catch {
        /* offline — the token is cleared locally regardless */
      }
    }
    clearTokens()
    // An unsent write must not outlive the session it was made in — it would fire under
    // whoever signs in next. This is the objection that kept `the-coupon`'s queue in
    // memory; persisting the queue is only defensible with this line here
    // (`DECISIONS.md` #44).
    await clearQueue()
    setProfile(null)
  }, [])

  const setPin = useCallback(
    async (newPin: string, currentPin?: string): Promise<{ error: string | null }> => {
      const response = await authFetch('/auth/pin', {
        method: 'POST',
        body: JSON.stringify({ newPin, currentPin: currentPin ?? null }),
      })
      if (!response.ok) {
        return { error: await errorMessage(response, 'Could not set PIN') }
      }
      // Changing a PIN revokes every refresh row, this session's included.
      clearTokens()
      setProfile(null)
      return { error: null }
    },
    [],
  )

  return (
    <AuthContext.Provider
      value={{
        profile,
        isLoading,
        isAuthenticated: profile !== null,
        signIn,
        signOut,
        setPin,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
