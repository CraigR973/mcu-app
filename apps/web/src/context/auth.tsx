import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { profileResponseSchema, tokenPairSchema, type ProfileResponse } from '@mcu/shared'

import {
  API_BASE,
  authFetch,
  clearTokens,
  getAccessToken,
  getRefreshToken,
  storeTokens,
} from '../lib/auth-tokens'

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
    const body = (await response.json()) as { detail?: string; error?: string }
    // A durably rate-limited login answers `{ error: "Rate limit exceeded: ..." }`,
    // not `{ detail: ... }` — reading only `detail` would turn a 429 into "your
    // details are wrong" and invite the retry the limit just refused.
    return body.error ?? body.detail ?? fallback
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
        clearTokens()
        setProfile(null)
        return
      }
      const parsed = profileResponseSchema.safeParse(await response.json())
      setProfile(parsed.success ? parsed.data : null)
    } catch {
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
      const parsed = tokenPairSchema.safeParse(await response.json())
      if (!parsed.success) {
        return { error: 'Unexpected response from the server' }
      }
      storeTokens(parsed.data.accessToken, parsed.data.refreshToken)
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
