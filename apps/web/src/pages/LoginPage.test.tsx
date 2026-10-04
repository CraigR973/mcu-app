// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const auth = vi.hoisted(() => ({
  isAuthenticated: false,
  signIn: vi.fn(),
}))
vi.mock('@/context/auth', () => ({
  useAuth: () => ({
    profile: null,
    isLoading: false,
    isAuthenticated: auth.isAuthenticated,
    isSessionUnavailable: false,
    signIn: auth.signIn,
    refresh: vi.fn(),
  }),
}))

import ProtectedRoute from '@/components/ProtectedRoute'
import { ThemeProvider } from '@/context/theme'

import LoginPage from './LoginPage'

const INVITE = '/movie-night/join/long-private-invite-token'

function Where() {
  const location = useLocation()
  return <output aria-label="Current page">{location.pathname + location.search}</output>
}

afterEach(() => {
  cleanup()
})

describe('an invite link reached while signed out — Batch T4, snag 11', () => {
  it('lands on that night after signing in, not on the front page', async () => {
    auth.isAuthenticated = false
    auth.signIn.mockImplementation(async () => {
      auth.isAuthenticated = true
      return { error: null }
    })
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={[INVITE]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/movie-night/join/:token" element={<ProtectedRoute><p>The night</p></ProtectedRoute>} />
          </Routes>
          <Where />
        </MemoryRouter>
      </ThemeProvider>,
    )
    expect(screen.getByLabelText('Current page').textContent).toBe('/login')

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Mark' } })
    fireEvent.change(screen.getByLabelText('PIN'), { target: { value: '8317' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enter the archive' }))

    await waitFor(() => expect(screen.getByLabelText('Current page').textContent).toBe(INVITE))
    expect(screen.getByText('The night')).not.toBeNull()
  })
})

describe("eBay's return address reached while signed out — Batch T8b", () => {
  it('keeps the one-time code through signing in', async () => {
    const RETURN = '/settings/ebay/connected?state=the-state&code=v%5E1.1%23code'
    auth.isAuthenticated = false
    auth.signIn.mockImplementation(async () => {
      auth.isAuthenticated = true
      return { error: null }
    })
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={[RETURN]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/settings/ebay/connected" element={<ProtectedRoute><p>Finishing</p></ProtectedRoute>} />
          </Routes>
          <Where />
        </MemoryRouter>
      </ThemeProvider>,
    )
    expect(screen.getByLabelText('Current page').textContent).toBe('/login')

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Mark' } })
    fireEvent.change(screen.getByLabelText('PIN'), { target: { value: '8317' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enter the archive' }))

    await waitFor(() => expect(screen.getByLabelText('Current page').textContent).toBe(RETURN))
    expect(screen.getByText('Finishing')).not.toBeNull()
  })
})
