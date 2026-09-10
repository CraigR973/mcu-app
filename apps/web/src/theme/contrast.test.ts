import { describe, expect, it } from 'vitest'

import { semanticTokens, type ResolvedTheme } from './tokens'

/**
 * WCAG 2.2 AA, asserted against the token source rather than a screenshot.
 *
 * The redesign's own audit left "both themes still require automated contrast
 * verification" open, and the first run found real failures: error text at 3.1:1 on a
 * dark card, champagne at 1.9:1 on cream, and four format badges below 4.5:1. Those are
 * the pairings this file now pins, so a future palette tweak fails the gate instead of
 * shipping.
 *
 * Ratios are computed the way a browser composites them — including the translucent
 * tints badges and state panels paint underneath their own text.
 */

type Rgb = [number, number, number]

function hslToRgb(token: string): Rgb {
  const [h, s, l] = token.split(' ')
  const hue = Number(h)
  const sat = Number(s.replace('%', '')) / 100
  const light = Number(l.replace('%', '')) / 100

  const c = (1 - Math.abs(2 * light - 1)) * sat
  const x = c * (1 - Math.abs(((hue / 60) % 2) - 1))
  const m = light - c / 2
  const sextant = Math.floor(hue / 60) % 6
  const [r, g, b] = [
    [c, x, 0],
    [x, c, 0],
    [0, c, x],
    [0, x, c],
    [x, 0, c],
    [c, 0, x],
  ][sextant]
  return [r + m, g + m, b + m]
}

function relativeLuminance([r, g, b]: Rgb): number {
  const channel = (v: number) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrast(fg: Rgb, bg: Rgb): number {
  const a = relativeLuminance(fg)
  const b = relativeLuminance(bg)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

/** What a `bg-<tone>/<alpha>` tint actually resolves to over an opaque surface. */
function composite(fg: Rgb, bg: Rgb, alpha: number): Rgb {
  return [0, 1, 2].map((i) => fg[i] * alpha + bg[i] * (1 - alpha)) as Rgb
}

const AA_TEXT = 4.5
const AA_NON_TEXT = 3

/** Every opaque surface a page can put text on. */
const SURFACES = ['--background', '--card', '--popover', '--surface-sunken'] as const

/** Tones that appear both as a filled surface and as a status word. */
const TONES = ['primary', 'destructive', 'success', 'warning', 'info', 'accent'] as const

/** Format badges: `text-quality-x` over `bg-quality-x/14`. */
const QUALITIES = ['4k', 'bluray', 'dvd', 'digital', 'hdr', 'audio'] as const

const THEMES: ResolvedTheme[] = ['light', 'dark']

describe.each(THEMES)('%s theme contrast', (theme) => {
  const token = (name: string): Rgb => {
    const value = semanticTokens[theme][name as keyof (typeof semanticTokens)[typeof theme]]
    if (!value) throw new Error(`${theme} theme is missing ${name}`)
    return hslToRgb(value)
  }

  it('renders body, card and popover text at AA', () => {
    expect(contrast(token('--foreground'), token('--background'))).toBeGreaterThanOrEqual(AA_TEXT)
    expect(contrast(token('--card-foreground'), token('--card'))).toBeGreaterThanOrEqual(AA_TEXT)
    expect(contrast(token('--popover-foreground'), token('--popover'))).toBeGreaterThanOrEqual(AA_TEXT)
  })

  it('keeps secondary metadata legible on every surface', () => {
    for (const surface of [...SURFACES, '--muted'] as const) {
      expect(contrast(token('--muted-foreground'), token(surface))).toBeGreaterThanOrEqual(AA_TEXT)
    }
  })

  it.each(TONES)('carries a %s label on its own filled surface', (tone) => {
    expect(contrast(token(`--${tone}-foreground`), token(`--${tone}`))).toBeGreaterThanOrEqual(AA_TEXT)
  })

  it.each(TONES)('reads %s as status text on plain and tinted surfaces', (tone) => {
    const text = token(`--${tone}-text`)
    for (const surface of SURFACES) {
      const plain = token(surface)
      expect(contrast(text, plain)).toBeGreaterThanOrEqual(AA_TEXT)
      // Badges and state panels tint the surface with the tone itself before
      // painting the label on top; that tint is what the reader actually sees.
      const tinted = composite(token(`--${tone}`), plain, 0.12)
      expect(contrast(text, tinted)).toBeGreaterThanOrEqual(AA_TEXT)
    }
  })

  it.each(QUALITIES)('reads the %s format badge over its own tint', (quality) => {
    const text = token(`--quality-${quality}`)
    for (const surface of ['--background', '--card', '--surface-sunken'] as const) {
      const tinted = composite(text, token(surface), 0.14)
      expect(contrast(text, tinted)).toBeGreaterThanOrEqual(AA_TEXT)
    }
  })

  it('gives form controls and focus rings a 3:1 boundary', () => {
    for (const surface of ['--background', '--card'] as const) {
      expect(contrast(token('--input'), token(surface))).toBeGreaterThanOrEqual(AA_NON_TEXT)
      expect(contrast(token('--ring'), token(surface))).toBeGreaterThanOrEqual(AA_NON_TEXT)
    }
  })
})
