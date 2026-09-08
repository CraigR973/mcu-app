import { useEffect, useState } from 'react'

/** The event Chromium fires when the app is installable. Not in lib.dom yet. */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

export type InstallState = 'available' | 'installed' | 'unsupported'

/**
 * Whether the app can be installed, and the means to do it.
 *
 * **This is the half phase 2.8 never had.** The April wizard's install step read
 * `window.__pwaInstallPrompt`, which nothing ever set — and could not have, because there
 * was no manifest and no service worker for `beforeinstallprompt` to fire against
 * (`STATUS.md` gotcha 5). Batch 8 supplied both; this captures the event.
 *
 * `unsupported` is the honest answer on iOS Safari, which never fires the event and
 * requires Share → Add to Home Screen. Saying so beats offering a button that does
 * nothing, which is the failure this batch exists to end.
 */
export function usePwaInstall(): {
  state: InstallState
  install: () => Promise<'accepted' | 'dismissed' | 'unavailable'>
} {
  const [event, setEvent] = useState<BeforeInstallPromptEvent | null>(null)
  const [installed, setInstalled] = useState(
    () =>
      typeof window !== 'undefined' &&
      (window.matchMedia('(display-mode: standalone)').matches ||
        // iOS reports standalone here rather than through the media query.
        (window.navigator as { standalone?: boolean }).standalone === true),
  )

  useEffect(() => {
    const capture = (e: Event) => {
      // Chromium shows its own mini-infobar unless the event is prevented, and then
      // gives no second chance — so the event has to be caught and kept, not observed.
      e.preventDefault()
      setEvent(e as BeforeInstallPromptEvent)
    }
    const onInstalled = () => {
      setInstalled(true)
      setEvent(null)
    }
    window.addEventListener('beforeinstallprompt', capture)
    window.addEventListener('appinstalled', onInstalled)
    return () => {
      window.removeEventListener('beforeinstallprompt', capture)
      window.removeEventListener('appinstalled', onInstalled)
    }
  }, [])

  async function install(): Promise<'accepted' | 'dismissed' | 'unavailable'> {
    if (event === null) return 'unavailable'
    await event.prompt()
    const { outcome } = await event.userChoice
    // The event is single-use; Chromium will fire a fresh one if it is still installable.
    setEvent(null)
    return outcome
  }

  return {
    state: installed ? 'installed' : event !== null ? 'available' : 'unsupported',
    install,
  }
}
