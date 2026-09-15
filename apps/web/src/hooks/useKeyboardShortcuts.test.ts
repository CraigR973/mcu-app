// @vitest-environment happy-dom
import { cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

const navigateMock = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => navigateMock }
})

import { useKeyboardShortcuts } from './useKeyboardShortcuts'

function press(key: string, init: KeyboardEventInit = {}) {
  document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init }))
}

function mountShortcuts(overrides: Partial<Parameters<typeof useKeyboardShortcuts>[0]> = {}) {
  const onOpenPalette = vi.fn()
  const onOpenHelp = vi.fn()
  renderHook(() =>
    useKeyboardShortcuts({
      isAdmin: false,
      suspended: false,
      onOpenPalette,
      onOpenHelp,
      ...overrides,
    }),
  )
  return { onOpenPalette, onOpenHelp }
}

afterEach(() => {
  cleanup()
  navigateMock.mockClear()
  document.body.innerHTML = ''
})

describe('useKeyboardShortcuts', () => {
  it('opens the command palette on Ctrl+K and Cmd+K', () => {
    const { onOpenPalette } = mountShortcuts()

    press('k', { ctrlKey: true })
    press('k', { metaKey: true })

    expect(onOpenPalette).toHaveBeenCalledTimes(2)
  })

  it('opens the help modal on "?"', () => {
    const { onOpenHelp } = mountShortcuts()
    press('?')
    expect(onOpenHelp).toHaveBeenCalledTimes(1)
  })

  it('navigates on the documented g-chords', () => {
    mountShortcuts()

    press('g')
    press('c')
    expect(navigateMock).toHaveBeenCalledWith('/movies')

    press('g')
    press('s')
    // Batch S3: `/stats` is a section of `/dashboard` now, which `g h` already reaches,
    // so `g s` took the destination the merge created instead of landing on a redirect.
    expect(navigateMock).toHaveBeenCalledWith('/settings')
  })

  it('drops a chord whose second key never arrives within the window', () => {
    vi.useFakeTimers()
    mountShortcuts()

    press('g')
    vi.advanceTimersByTime(801)
    press('h')

    expect(navigateMock).not.toHaveBeenCalled()
    vi.useRealTimers()
  })

  it('only navigates "n" to Add a disc for an admin', () => {
    mountShortcuts({ isAdmin: false })
    press('n')
    expect(navigateMock).not.toHaveBeenCalled()

    cleanup()
    navigateMock.mockClear()

    mountShortcuts({ isAdmin: true })
    press('n')
    expect(navigateMock).toHaveBeenCalledWith('/collection/add')
  })

  it('does not fire bare-key shortcuts while the person is typing', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    mountShortcuts({ isAdmin: true })
    press('n')

    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('still opens the palette with Cmd+K while typing', () => {
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.focus()

    const { onOpenPalette } = mountShortcuts()
    press('k', { metaKey: true })

    expect(onOpenPalette).toHaveBeenCalledTimes(1)
  })

  it('suspends bare-key shortcuts while a modal already owns the keyboard', () => {
    const { onOpenHelp } = mountShortcuts({ suspended: true })
    press('?')
    press('g')
    press('c')

    expect(onOpenHelp).not.toHaveBeenCalled()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('dispatches mcu:focus-search on "/" instead of focusing anything itself', () => {
    mountShortcuts()
    const handler = vi.fn()
    window.addEventListener('mcu:focus-search', handler)

    press('/')

    expect(handler).toHaveBeenCalledTimes(1)
    window.removeEventListener('mcu:focus-search', handler)
  })
})
