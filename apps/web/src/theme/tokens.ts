/**
 * MCU's visual foundation.
 *
 * Values live in TypeScript so the first render, the theme switcher and any future
 * native/PWA chrome all consume the same source. Tailwind names the semantic variables;
 * it never owns a second copy of the palette.
 *
 * Brand colours are intentionally distinct from semantic colours. The later identity
 * pass can tune the former without turning every warning, focus ring or destructive
 * action into a logo-colour decision.
 */

export type ResolvedTheme = 'light' | 'dark'
export type ThemePreference = ResolvedTheme | 'system'

export const brandTokens = {
  ink: '24 15% 7%',
  cream: '40 33% 96%',
  burgundy: '344 48% 31%',
  champagne: '41 43% 63%',
} as const

type TokenMap = Record<`--${string}`, string>

const lightTokens: TokenMap = {
  '--background': '40 31% 95%',
  '--foreground': '28 17% 11%',
  '--card': '42 38% 98%',
  '--card-foreground': '28 17% 11%',
  '--popover': '42 45% 99%',
  '--popover-foreground': '28 17% 11%',
  '--surface-raised': '42 38% 98%',
  '--surface-sunken': '38 23% 91%',
  '--primary': '344 48% 31%',
  '--primary-foreground': '42 45% 98%',
  '--primary-text': '344 48% 31%',
  '--secondary': '38 23% 89%',
  '--secondary-foreground': '30 17% 18%',
  '--muted': '38 23% 90%',
  '--muted-foreground': '31 12% 38%',
  '--accent': '41 43% 63%',
  '--accent-foreground': '28 20% 11%',
  '--accent-text': '41 43% 31%',
  '--destructive': '356 55% 39%',
  '--destructive-foreground': '0 0% 100%',
  '--destructive-text': '356 55% 39%',
  '--success': '151 35% 31%',
  '--success-foreground': '0 0% 100%',
  '--success-text': '151 35% 30%',
  '--warning': '35 64% 37%',
  '--warning-foreground': '35 80% 98%',
  '--warning-text': '35 64% 30%',
  '--info': '207 37% 39%',
  '--info-foreground': '0 0% 100%',
  '--info-text': '207 37% 37%',
  '--border': '35 20% 79%',
  '--input': '35 15% 53%',
  '--ring': '344 48% 31%',
  '--shadow-colour': '24 20% 12%',
  '--quality-4k': '186 52% 28%',
  '--quality-bluray': '229 52% 43%',
  '--quality-dvd': '30 9% 36%',
  '--quality-digital': '151 39% 29%',
  '--quality-hdr': '35 70% 29%',
  '--quality-audio': '278 31% 40%',
}

const darkTokens: TokenMap = {
  '--background': '24 15% 6%',
  '--foreground': '39 28% 91%',
  '--card': '26 16% 9%',
  '--card-foreground': '39 28% 91%',
  '--popover': '27 17% 11%',
  '--popover-foreground': '39 28% 91%',
  '--surface-raised': '27 17% 12%',
  '--surface-sunken': '24 14% 4%',
  '--primary': '344 40% 58%',
  '--primary-foreground': '24 20% 8%',
  '--primary-text': '344 40% 63%',
  '--secondary': '28 15% 16%',
  '--secondary-foreground': '39 24% 88%',
  '--muted': '27 14% 15%',
  '--muted-foreground': '33 13% 64%',
  '--accent': '41 47% 66%',
  '--accent-foreground': '24 20% 8%',
  '--accent-text': '41 47% 66%',
  '--destructive': '356 54% 47%',
  '--destructive-foreground': '0 0% 100%',
  '--destructive-text': '356 54% 65%',
  '--success': '151 38% 43%',
  '--success-foreground': '150 45% 7%',
  '--success-text': '151 38% 46%',
  '--warning': '38 73% 58%',
  '--warning-foreground': '30 35% 9%',
  '--warning-text': '38 73% 58%',
  '--info': '205 52% 61%',
  '--info-foreground': '210 45% 8%',
  '--info-text': '205 52% 61%',
  '--border': '29 16% 22%',
  '--input': '31 15% 38%',
  '--ring': '41 47% 66%',
  '--shadow-colour': '0 0% 0%',
  '--quality-4k': '184 58% 43%',
  '--quality-bluray': '229 67% 68%',
  '--quality-dvd': '32 11% 61%',
  '--quality-digital': '151 46% 47%',
  '--quality-hdr': '41 78% 61%',
  '--quality-audio': '278 50% 68%',
}

export const semanticTokens = {
  light: lightTokens,
  dark: darkTokens,
} as const

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference !== 'system') return preference
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function applyThemeTokens(theme: ResolvedTheme): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  const tokens = semanticTokens[theme]

  for (const [name, value] of Object.entries({
    '--brand-ink': brandTokens.ink,
    '--brand-cream': brandTokens.cream,
    '--brand-burgundy': brandTokens.burgundy,
    '--brand-champagne': brandTokens.champagne,
    ...tokens,
  })) {
    root.style.setProperty(name, value)
  }

  root.classList.toggle('dark', theme === 'dark')
  root.dataset.theme = theme
  root.style.colorScheme = theme
  document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute(
    'content',
    theme === 'dark' ? 'hsl(24 15% 6%)' : 'hsl(40 31% 95%)',
  )
}
