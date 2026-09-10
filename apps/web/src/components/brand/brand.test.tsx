// @vitest-environment happy-dom
import { useEffect, type ReactNode } from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider, useTheme } from '@/context/theme'
import type { ResolvedTheme } from '@/theme/tokens'

import { BrandLockup } from './BrandLockup'
import { BrandMark, markAsset } from './BrandMark'

/**
 * What is worth pinning down here is the identity's own rules, not React plumbing: which
 * drawn master each size gets, that a decorative mark stays out of the accessibility tree
 * while a standalone one has a name, and that both reserve their box before the file
 * arrives. Every one of those is a rule an ordinary refactor can break silently.
 */

/**
 * The theme preference is read from storage once, when `context/theme` is first imported —
 * a page load reads it, a later `localStorage.setItem` does not. So the light-surface
 * cases drive the provider through its own API, which is also the path a person takes
 * when they hit the theme toggle.
 */
function SetTheme({ theme }: { theme: ResolvedTheme }) {
  const { setTheme } = useTheme()
  useEffect(() => setTheme(theme), [theme, setTheme])
  return null
}

function renderWithTheme(node: ReactNode, theme: ResolvedTheme = 'dark') {
  return render(
    <ThemeProvider>
      <SetTheme theme={theme} />
      {node}
    </ThemeProvider>,
  )
}

afterEach(() => {
  cleanup()
  localStorage.clear()
})

describe('markAsset', () => {
  it.each([
    [512, 'app-icon-concept-art'],
    [192, 'app-icon-concept-art'],
    [191, 'stack-mark.svg'],
    [128, 'stack-mark.svg'],
    [127, 'stack-mark-compact.svg'],
    [96, 'stack-mark-compact.svg'],
    [32, 'stack-mark-compact.svg'],
    [31, 'micro-mark-16.svg'],
    [16, 'micro-mark-16.svg'],
  ])('draws %ipx with %s', (size, expected) => {
    expect(markAsset(size, 'dark')).toContain(expected)
  })

  it('pairs the vector tiers with the surface, and leaves the emblem alone', () => {
    expect(markAsset(128, 'light')).toContain('stack-mark-light.svg')
    expect(markAsset(64, 'light')).toContain('stack-mark-compact-light.svg')
    // The concept-art emblem is a platform icon with one approved field.
    expect(markAsset(512, 'light')).toBe(markAsset(512, 'dark'))
  })

  it('never asks the concept art to draw below its 192px minimum', () => {
    for (let size = 8; size < 192; size += 1) {
      expect(markAsset(size, 'dark')).not.toContain('concept-art')
    }
  })
})

describe('BrandMark', () => {
  it('is decorative without a label, so brand text beside it is not read twice', () => {
    renderWithTheme(<BrandMark size={32} />)
    expect(screen.queryByRole('img')).toBeNull()
    expect(document.querySelector('img')?.getAttribute('alt')).toBe('')
  })

  it('has an accessible name when it stands alone', () => {
    renderWithTheme(<BrandMark size={128} label="Mark's Cinematic Universe" />)
    expect(screen.getByRole('img', { name: "Mark's Cinematic Universe" })).toBeTruthy()
  })

  it('reserves its box so nothing reflows while the artwork decodes', () => {
    renderWithTheme(<BrandMark size={36} />)
    const img = document.querySelector('img')!
    expect(img.getAttribute('width')).toBe('36')
    expect(img.getAttribute('height')).toBe('36')
    expect(img.style.width).toBe('36px')
    expect(img.style.height).toBe('36px')
  })

  it('picks the light artwork on a light surface', () => {
    renderWithTheme(<BrandMark size={64} />, 'light')
    expect(document.querySelector('img')?.getAttribute('src')).toContain('compact-light')
  })
})

describe('BrandLockup', () => {
  it('defaults each variant to its approved minimum width', () => {
    renderWithTheme(<BrandLockup variant="horizontal" />)
    const horizontal = document.querySelector('img')!
    expect(horizontal.getAttribute('width')).toBe('280')
    // 1600 x 420 — the height follows the artwork, not the container.
    expect(horizontal.getAttribute('height')).toBe('74')

    cleanup()
    renderWithTheme(<BrandLockup variant="stacked" />)
    const stacked = document.querySelector('img')!
    expect(stacked.getAttribute('width')).toBe('320')
    expect(stacked.getAttribute('height')).toBe('320')
  })

  it('follows the surface', () => {
    renderWithTheme(<BrandLockup variant="horizontal" />, 'light')
    expect(document.querySelector('img')?.getAttribute('src')).toContain('horizontal-lockup-light')
  })

  it('keeps its aspect ratio when a narrow container constrains the requested width', () => {
    renderWithTheme(<BrandLockup variant="horizontal" width={440} />)
    const lockup = document.querySelector('img')!

    expect(lockup.style.maxWidth).toBe('')
    expect(lockup.className).toContain('max-w-full')
    expect(lockup.style.height).toBe('auto')
    expect(Number.parseFloat(lockup.style.aspectRatio)).toBeCloseTo(1600 / 420)
  })

  describe('below the approved minimum', () => {
    let warn: ReturnType<typeof vi.spyOn>

    beforeEach(() => {
      warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    })

    afterEach(() => warn.mockRestore())

    it('warns in development when a call site quietly shrinks it', () => {
      renderWithTheme(<BrandLockup variant="horizontal" width={180} />)
      expect(warn).toHaveBeenCalledTimes(1)
      expect(String(warn.mock.calls[0][0])).toContain('180px')
    })

    it('stays quiet when the trade-off is recorded', () => {
      renderWithTheme(
        <BrandLockup variant="horizontal" width={240} underMinimumReason="The sidebar is 272px wide." />,
      )
      expect(warn).not.toHaveBeenCalled()
    })
  })
})
