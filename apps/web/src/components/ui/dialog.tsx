import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
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
  const labelId = useId()

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    // A fallback focus target for a dialog with no input of its own (the shortcuts
    // help modal). One that autofocuses something more specific — the command
    // palette's search box — moves focus again itself right after this.
    panelRef.current?.focus()

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }

      if (e.key === 'Tab' && panelRef.current) {
        const focusable = Array.from(
          panelRef.current.querySelectorAll<HTMLElement>(
            'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
          ),
        )
        if (focusable.length === 0) {
          e.preventDefault()
          panelRef.current.focus()
          return
        }
        const first = focusable[0]
        const last = focusable[focusable.length - 1]
        if (e.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.body.style.overflow = previousOverflow
      previouslyFocused?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-brand-ink/70 px-0 backdrop-blur-[2px] sm:items-start sm:px-4 sm:pt-[10vh]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelId}
        tabIndex={-1}
        className={cn(
          'safe-bottom max-h-[92dvh] w-full overflow-y-auto rounded-t-xl border border-border bg-popover shadow-lift focus:outline-none sm:max-w-lg sm:rounded-xl',
          className,
        )}
      >
        <span id={labelId} className="sr-only">{label}</span>
        {children}
      </div>
    </div>,
    document.body,
  )
}
