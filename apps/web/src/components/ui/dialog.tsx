import { useEffect, useRef, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface DialogProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  className?: string
  /** Accessible name — there is no visible dialog title in the command palette, so
   *  this is the only way a screen reader knows what just opened. */
  label: string
}

/**
 * A minimal accessible modal shell: no portal, no focus-trap library. Escape closes it
 * and focus returns to whatever opened it — §7.8's "keyboard-reachable, nothing needs
 * a mouse to close" is the whole requirement this batch has to meet, and every current
 * caller (command palette, shortcuts help) autofocuses its own first element anyway.
 */
export function Dialog({ open, onClose, children, className, label }: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    // A fallback focus target for a dialog with no input of its own (the shortcuts
    // help modal). One that autofocuses something more specific — the command
    // palette's search box — moves focus again itself right after this.
    panelRef.current?.focus()

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      previouslyFocused?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 px-4 pt-[10vh]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        className={cn(
          'w-full max-w-lg rounded-lg border border-border bg-popover shadow-lg focus:outline-none',
          className,
        )}
      >
        {children}
      </div>
    </div>
  )
}
