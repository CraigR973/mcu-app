// @vitest-environment happy-dom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { usePwaInstall } from './usePwaInstall'

/**
 * The install step's infrastructure, which phase 2.8 never had.
 *
 * The April wizard read `window.__pwaInstallPrompt` — a property nothing set, and nothing
 * could have set, because there was no manifest and no service worker for
 * `beforeinstallprompt` to fire against (`STATUS.md` gotcha 5). This batch's acceptance
 * criterion is exactly "no step reads a property nothing sets", so the capture is the
 * part that has to be proved.
 *
 * Scoped to jsdom by the docblock above: the rest of the web suite runs in node, and
 * this is the one file that genuinely needs window events.
 */

function installEvent(outcome: 'accepted' | 'dismissed' = 'accepted') {
  const event = new Event('beforeinstallprompt') as Event & {
    prompt: () => Promise<void>
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
  }
  event.prompt = vi.fn().mockResolvedValue(undefined)
  event.userChoice = Promise.resolve({ outcome })
  return event
}

afterEach(() => {
  // Explicit, because Testing Library only registers its own auto-cleanup when vitest
  // `globals` is on — and this project does not enable them. Without it, every hook
  // mounted by an earlier test stays mounted and keeps its window listener, which makes
  // "the listener went away" unprovable and every count wrong.
  cleanup()
  vi.restoreAllMocks()
})

describe('usePwaInstall', () => {
  it('reports unsupported until the browser says the app is installable', () => {
    const { result } = renderHook(() => usePwaInstall())

    // iOS Safari never fires the event, and this is the state it stays in — which is why
    // the wizard shows instructions there rather than a button that does nothing.
    expect(result.current.state).toBe('unsupported')
  })

  it('captures the event and prevents its default, so it can be offered later', async () => {
    const { result, unmount } = renderHook(() => usePwaInstall())
    const event = installEvent()
    const prevented = vi.spyOn(event, 'preventDefault')

    await act(async () => {
      window.dispatchEvent(event)
    })

    expect(result.current.state).toBe('available')
    // Chromium shows its own mini-infobar unless the event is prevented, and then gives
    // no second chance — an unprevented event cannot be re-offered from a wizard step.
    // Asserted as "was prevented" rather than a call count: how many times React mounts
    // an effect is React's business, and pinning it would test the renderer, not this.
    expect(prevented).toHaveBeenCalled()

    // And the listener goes when the hook does, so a wizard opened twice does not leave
    // a handler behind holding a stale event.
    unmount()
    const after = installEvent()
    const afterSpy = vi.spyOn(after, 'preventDefault')
    window.dispatchEvent(after)
    expect(afterSpy).not.toHaveBeenCalled()
  })

  it('prompts on demand and reports what the person chose', async () => {
    const { result } = renderHook(() => usePwaInstall())
    const event = installEvent('dismissed')
    await act(async () => {
      window.dispatchEvent(event)
    })

    let outcome: string | undefined
    await act(async () => {
      outcome = await result.current.install()
    })

    expect(event.prompt).toHaveBeenCalledTimes(1)
    expect(outcome).toBe('dismissed')
    // The event is single-use; holding a spent one would offer a button that does nothing.
    expect(result.current.state).toBe('unsupported')
  })

  it('says "unavailable" rather than throwing when there is nothing to prompt with', async () => {
    const { result } = renderHook(() => usePwaInstall())

    let outcome: string | undefined
    await act(async () => {
      outcome = await result.current.install()
    })

    expect(outcome).toBe('unavailable')
  })

  it('reports installed once the browser says so', async () => {
    const { result } = renderHook(() => usePwaInstall())
    await act(async () => {
      window.dispatchEvent(installEvent())
      window.dispatchEvent(new Event('appinstalled'))
    })

    expect(result.current.state).toBe('installed')
  })
})
