// @vitest-environment happy-dom
import { act, cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider, useAuth } from './auth'

type AuthValue = ReturnType<typeof useAuth>

function Probe({ capture }: { capture: (value: AuthValue) => void }) {
  const auth = useAuth()
  capture(auth)
  return null
}

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('AuthProvider outage handling', () => {
  it('returns a useful transport error instead of rejecting sign-in', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    let auth: AuthValue | undefined
    render(<AuthProvider><Probe capture={(value) => { auth = value }} /></AuthProvider>)
    await waitFor(() => expect(auth?.isLoading).toBe(false))

    let result: { error: string | null } | undefined
    await act(async () => { result = await auth?.signIn('Craig', '1234') })

    expect(result?.error).toMatch(/could not reach the archive/i)
    expect(auth?.isAuthenticated).toBe(false)
  })

  it('keeps a cached profile usable when the profile refresh has no network response', async () => {
    localStorage.setItem('mcu.accessToken', 'cached-access-token')
    localStorage.setItem('mcu.refreshToken', 'cached-refresh-token')
    localStorage.setItem('mcu.lastProfile', JSON.stringify({
      id: '11111111-1111-4111-8111-111111111111',
      displayName: 'Craig',
      role: 'admin',
      hasPin: true,
      onboardingCompleted: true,
    }))
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    let auth: AuthValue | undefined
    render(<AuthProvider><Probe capture={(value) => { auth = value }} /></AuthProvider>)

    await waitFor(() => expect(auth?.isLoading).toBe(false))
    expect(auth?.profile?.displayName).toBe('Craig')
    expect(auth?.isSessionUnavailable).toBe(false)
  })

  it('distinguishes an unconfirmed session from being signed out', async () => {
    localStorage.setItem('mcu.accessToken', 'uncached-access-token')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    let auth: AuthValue | undefined
    render(<AuthProvider><Probe capture={(value) => { auth = value }} /></AuthProvider>)

    await waitFor(() => expect(auth?.isLoading).toBe(false))
    expect(auth?.isAuthenticated).toBe(false)
    expect(auth?.isSessionUnavailable).toBe(true)
    expect(localStorage.getItem('mcu.accessToken')).toBe('uncached-access-token')
  })
})

