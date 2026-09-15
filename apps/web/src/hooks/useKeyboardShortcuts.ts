import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

/** §7.5's `g` chords. Not every documented target is reachable without a role check —
 *  `n` (add new item) is admin-only and enforced by the caller, same as the sidebar. */
const GO_TARGETS: Record<string, string> = {
  h: '/dashboard',
  c: '/movies',
  w: '/wanted',
  // Batch S3. `g s` was "go to stats", and stats is a *section* of `/dashboard` now —
  // which `g h` already reaches. Rather than leave the chord landing on a redirect to
  // somewhere another chord goes, it takes the destination the merge created.
  s: '/settings',
}

/** How long the second key of a `g` chord has to land. */
const CHORD_WINDOW_MS = 800

function isTypingTarget(el: Element | null): boolean {
  if (!el) return false
  if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return true
  return (el as HTMLElement).isContentEditable
}

interface Options {
  isAdmin: boolean
  /** True while the palette or the shortcuts help modal already owns the keyboard —
   *  bare-key shortcuts stay off so typing in the palette's own search box can't
   *  double as a shortcut trigger. */
  suspended: boolean
  onOpenPalette: () => void
  onOpenHelp: () => void
}

/** §7.5's global shortcuts, mounted once in AppLayout. `/` doesn't focus anything
 *  itself — it dispatches `mcu:focus-search`, which SearchBar listens for, so there is
 *  still exactly one place deciding what counts as "typing" before a shortcut fires. */
export function useKeyboardShortcuts({ isAdmin, suspended, onOpenPalette, onOpenHelp }: Options): void {
  const navigate = useNavigate()
  const awaitingGoTarget = useRef(false)
  const chordTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    function clearChord() {
      awaitingGoTarget.current = false
      if (chordTimer.current) {
        clearTimeout(chordTimer.current)
        chordTimer.current = null
      }
    }

    function onKeyDown(e: KeyboardEvent) {
      // The one shortcut that must work from anywhere, typing included — it's the
      // documented way out of every other state.
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        onOpenPalette()
        return
      }

      if (suspended || e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(document.activeElement)) {
        return
      }

      if (awaitingGoTarget.current) {
        const target = GO_TARGETS[e.key]
        clearChord()
        if (target) navigate(target)
        return
      }

      if (e.key === '/') {
        e.preventDefault()
        window.dispatchEvent(new Event('mcu:focus-search'))
        return
      }

      if (e.key === '?') {
        onOpenHelp()
        return
      }

      if (e.key === '.') {
        e.preventDefault()
        navigate('/assistant')
        return
      }

      if (e.key === 'n' && isAdmin) {
        navigate('/collection/add')
        return
      }

      if (e.key === 'g') {
        awaitingGoTarget.current = true
        chordTimer.current = setTimeout(clearChord, CHORD_WINDOW_MS)
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      clearChord()
    }
  }, [navigate, isAdmin, suspended, onOpenPalette, onOpenHelp])
}
