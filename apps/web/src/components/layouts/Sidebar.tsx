import { useEffect, useRef } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { LogOut, X } from 'lucide-react'
import { COLLECTION_ICONS } from '@/components/collections/icons'
import { fetchSmartCollections } from '@/lib/api'
import { useAuth } from '@/context/auth'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { adminNavGroup, navGroups } from '@/lib/nav-items'
import { cn } from '@/lib/utils'

interface Props {
  open: boolean
  onClose: () => void
}

const LINK_CLS =
  'group flex min-h-10 items-center gap-3 rounded-md border border-transparent px-3 py-2 text-sm font-semibold transition-colors'

export default function Sidebar({ open, onClose }: Props) {
  const { profile, signOut } = useAuth()
  const closeRef = useRef<HTMLButtonElement>(null)
  const panelRef = useRef<HTMLElement>(null)

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
      if (event.key !== 'Tab' || !panelRef.current) return
      const focusable = Array.from(panelRef.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'))
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('keydown', closeOnEscape)
      document.body.style.overflow = previousOverflow
      previouslyFocused?.focus?.()
    }
  }, [open, onClose])

  // §6.31: "Smart collections appear in the sidebar with custom icons." Failing quietly
  // is right here — the sidebar is navigation, and a network problem should not cost
  // the person the links that do work.
  const { data: collections } = useQuery({
    queryKey: ['smart-collections'],
    queryFn: () => fetchSmartCollections(),
    staleTime: 5 * 60 * 1000,
  })
  const saved = collections?.items ?? []

  return (
    <>
      {/* Backdrop (mobile) */}
      {open && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-40 cursor-default bg-brand-ink/70 backdrop-blur-[2px] lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <aside
        ref={panelRef}
        role={open ? 'dialog' : undefined}
        aria-modal={open || undefined}
        aria-label={open ? 'Application navigation' : undefined}
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-[17rem] max-w-[86vw] flex-col border-r border-border bg-card transition-[transform,visibility] duration-200',
          'lg:relative lg:translate-x-0',
          open ? 'visible translate-x-0' : 'invisible -translate-x-full lg:visible',
        )}
      >
        {/* Header */}
        <div className="flex min-h-[5.5rem] items-center justify-between border-b border-border px-4 py-4">
          <Link to="/movies" onClick={onClose} className="flex min-w-0 items-center rounded-md">
            {/* Personalised poster stack with real photos from Mark's collection */}
            <img
              src="/brand/personalised-poster-icon-512.png"
              alt="Mark's Cinematic Universe collection"
              className="h-20 w-auto rounded-md shadow-md"
            />
          </Link>
          <button
            ref={closeRef}
            type="button"
            aria-label="Close menu"
            className="touch-target -mr-2 flex items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"
            onClick={onClose}
          >
            <X size={20} aria-hidden />
          </button>
        </div>

        {/* Nav */}
        <nav aria-label="Application destinations" className="flex-1 overflow-y-auto px-3 py-4">
          {navGroups.map((group) => (
            <div key={group.label} className="mb-5 last:mb-0">
              <p className="mb-1 px-3 text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {group.label}
              </p>
              <div className="space-y-0.5">
                {group.items.map(({ label, path, icon: Icon }) => (
                  <NavLink
                    key={path}
                    to={path}
                    onClick={onClose}
                    className={({ isActive }) =>
                      cn(
                        LINK_CLS,
                        isActive
                          ? 'border-primary/15 bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )
                    }
                  >
                    <Icon className="h-[1.125rem] w-[1.125rem] shrink-0 opacity-80 group-hover:opacity-100" aria-hidden />
                    <span className="truncate">{label}</span>
                  </NavLink>
                ))}
              </div>
            </div>
          ))}

          {profile?.role === 'admin' && (
            <div className="mb-5 border-t border-border pt-4">
              <p className="mb-1 px-3 text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                {adminNavGroup.label}
              </p>
              <div className="space-y-0.5">
                {adminNavGroup.items.map(({ label, path, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    LINK_CLS,
                    isActive
                      ? 'border-primary/15 bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  )
                }
              >
                <Icon className="h-[1.125rem] w-[1.125rem] shrink-0 opacity-80" aria-hidden />
                <span className="truncate">{label}</span>
              </NavLink>
                ))}
              </div>
            </div>
          )}

          {saved.length > 0 && (
            <>
              <p className="mb-1 border-t border-border px-3 pb-1 pt-4 text-[0.625rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Saved collections
              </p>
              {saved.map((collection) => {
                const Icon = COLLECTION_ICONS[collection.icon]
                return (
                  <NavLink
                    key={collection.id}
                    to={`/collections/${collection.id}`}
                    onClick={onClose}
                    className={({ isActive }) =>
                      cn(
                        LINK_CLS,
                        isActive
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                      )
                    }
                  >
                    <Icon className="h-[1.125rem] w-[1.125rem]" aria-hidden />
                    <span className="truncate">{collection.name}</span>
                  </NavLink>
                )
              })}
            </>
          )}
        </nav>

        {/* Footer */}
        <div className="safe-bottom space-y-2 border-t border-border bg-surface-sunken/45 px-3 py-3">
          <div className="flex items-center gap-3 rounded-md px-2 py-1">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-secondary font-display font-semibold text-secondary-foreground">
              {profile?.displayName?.slice(0, 1).toUpperCase() ?? '—'}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold text-foreground">{profile?.displayName ?? 'Local preview'}</span>
              <span className="block text-[0.6875rem] capitalize text-muted-foreground">{profile?.role ?? 'Loading profile'}</span>
            </span>
            <ThemeToggle />
          </div>
          <Button variant="ghost" size="sm" className="w-full justify-start" onClick={signOut}>
            <LogOut aria-hidden />
            Sign out
          </Button>
        </div>
      </aside>
    </>
  )
}
