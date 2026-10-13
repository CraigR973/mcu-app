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
import { clearCachedApiReads } from '@/lib/api-cache-route'

interface AuthContextValue {
  profile: ProfileResponse | null
  isLoading: boolean
  isAuthenticated: boolean
  /** Credentials exist, but the server and any local profile cache could not establish
   *  which role owns them. This is not the same as being signed out. */
  isSessionUnavailable: boolean
  signIn: (displayName: string, pin: string) => Promise<{ error: string | null }>
  signOut: () => Promise<void>
  /** Re-read the profile. The wizard calls it so the route gate sees the new state. */
  refresh: () => Promise<void>
  setPin: (newPin: string, currentPin?: string) => Promise<{ error: string | null }>
}

const AuthContext = createContext<AuthContextValue | null>(null)
const PROFILE_CACHE_KEY = 'mcu.lastProfile'

function cachedProfile(): ProfileResponse | null {
  try {
    return profileResponseSchema.parse(JSON.parse(localStorage.getItem(PROFILE_CACHE_KEY) ?? 'null'))
  } catch {
    return null
  }
}

function storeProfile(profile: ProfileResponse | null): void {
  try {
    if (profile) localStorage.setItem(PROFILE_CACHE_KEY, JSON.stringify(profile))
    else localStorage.removeItem(PROFILE_CACHE_KEY)
  } catch {
    // A live session continues even when storage is unavailable.
  }
}

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
  const [isSessionUnavailable, setIsSessionUnavailable] = useState(false)

  const loadProfile = useCallback(async () => {
    if (!getAccessToken() && !getRefreshToken()) {
      setProfile(null)
      storeProfile(null)
      setIsSessionUnavailable(false)
      setIsLoading(false)
      return null
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
        if (shouldEndSession(response.status)) {
          clearTokens()
          storeProfile(null)
          setProfile(null)
          setIsSessionUnavailable(false)
          return null
        }
        const cached = cachedProfile()
        setProfile(cached)
        setIsSessionUnavailable(cached === null)
        return cached
      }
      const body: unknown = await response.json()
      const nextProfile = profileResponseSchema.parse(body)
      storeProfile(nextProfile)
      setProfile(nextProfile)
      setIsSessionUnavailable(false)
      return nextProfile
    } catch {
      // Network failure. The session is intact; we simply cannot confirm it right now.
      const cached = cachedProfile()
      setProfile(cached)
      setIsSessionUnavailable(cached === null)
      return cached
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadProfile()
  }, [loadProfile])

  const signIn = useCallback(
    async (displayName: string, pin: string): Promise<{ error: string | null }> => {
      let response: Response
      try {
        response = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ displayName, pin }),
        })
      } catch {
        return { error: 'Could not reach the archive. Check your connection and try again.' }
      }
      if (!response.ok) {
        return { error: await errorMessage(response, 'Sign in failed') }
      }
      try {
        const body: unknown = await response.json()
        const tokens = tokenPairSchema.parse(body)
        // A different person may be signing in on the same device. Never let their
        // profile become the fallback while the new session is being established.
        storeProfile(null)
        storeTokens(tokens.accessToken, tokens.refreshToken)
      } catch {
        return { error: 'Unexpected response from the server' }
      }
      const loaded = await loadProfile()
      if (!loaded) return { error: 'Signed in, but the archive could not confirm your profile. Try again when the connection is stable.' }
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
    storeProfile(null)
    // An unsent write must not outlive the session it was made in — it would fire under
    // whoever signs in next. This is the objection that kept `the-coupon`'s queue in
    // memory; persisting the queue is only defensible with this line here
    // (`DECISIONS.md` #44).
    await clearQueue()
    // Batch X8: the API answers kept for offline reading go too, so whoever signs in next
    // on this phone finds none of them.
    await clearCachedApiReads()
    setProfile(null)
    setIsSessionUnavailable(false)
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
      storeProfile(null)
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
        isSessionUnavailable,
        signIn,
        signOut,
        setPin,
        refresh: async () => { await loadProfile() },
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
