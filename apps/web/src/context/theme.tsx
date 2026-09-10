import { createContext, useContext, useEffect, useState } from 'react'

import {
  applyThemeTokens,
  resolveTheme,
  type ResolvedTheme,
  type ThemePreference,
} from '@/theme/tokens'

interface ThemeContextValue {
  theme: ThemePreference
  resolvedTheme: ResolvedTheme
  setTheme: (theme: ThemePreference) => void
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

const STORAGE_KEY = 'mcu-theme'

function storedPreference(): ThemePreference {
  if (typeof localStorage === 'undefined') return 'dark'
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') return stored
  } catch {
    // Storage can be unavailable in private browsing; the in-memory preference works.
  }
  return 'dark'
}

const initialPreference = storedPreference()
const initialResolved = resolveTheme(initialPreference)
applyThemeTokens(initialResolved)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<ThemePreference>(initialPreference)
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(initialResolved)

  useEffect(() => {
    const media = typeof window.matchMedia === 'function'
      ? window.matchMedia('(prefers-color-scheme: dark)')
      : null
    const apply = () => {
      const resolved = resolveTheme(theme)
      setResolvedTheme(resolved)
      applyThemeTokens(resolved)
    }

    apply()
    if (theme === 'system') media?.addEventListener('change', apply)
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // The current tab still honours the choice when storage is unavailable.
    }

    return () => media?.removeEventListener('change', apply)
  }, [theme])

  const toggleTheme = () =>
    setTheme((preference) => (resolveTheme(preference) === 'dark' ? 'light' : 'dark'))

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
