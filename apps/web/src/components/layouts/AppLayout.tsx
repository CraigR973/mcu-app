import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Command, Menu, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import Sidebar from './Sidebar'
import CommandPalette from '@/components/CommandPalette'
import { FloatingChatButton } from '@/components/FloatingChatButton'
import ShortcutsHelpModal from '@/components/ShortcutsHelpModal'
import ErrorBoundary from '@/components/ErrorBoundary'
import OfflineBanner from '@/components/OfflineBanner'
import SearchBar from '@/components/SearchBar'
import { useAuth } from '@/context/auth'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { startAutoFlush } from '@/lib/sync'
import { MobileTabBar } from './MobileTabBar'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/brand/BrandMark'

interface Props {
  children: ReactNode
}

export default function AppLayout({ children }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const queryClient = useQueryClient()
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const closeSidebar = useCallback(() => setSidebarOpen(false), [])

  useKeyboardShortcuts({
    isAdmin,
    suspended: paletteOpen || helpOpen,
    onOpenPalette: () => setPaletteOpen(true),
    onOpenHelp: () => setHelpOpen(true),
  })

  // Reconnecting is the moment the queue can move, and the only one the app gets for
  // free. Registered on the shell rather than on a page so a queued edit is not stranded
  // by the person navigating away from wherever they made it.
  useEffect(
    () =>
      startAutoFlush((result) => {
        if (result.sent === 0) return
        void queryClient.invalidateQueries({ queryKey: ['movies'] })
        void queryClient.invalidateQueries({ queryKey: ['search'] })
        void queryClient.invalidateQueries({ queryKey: ['facets'] })
        void queryClient.invalidateQueries({ queryKey: ['movie-copies'] })
      }),
    [queryClient],
  )

  return (
    <div className="flex h-[100dvh] min-h-0 overflow-hidden bg-background text-foreground">
      <a href="#main-content" className="fixed left-3 top-3 z-[100] -translate-y-24 rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground shadow-lift focus:translate-y-0">Skip to content</a>
      <Sidebar open={sidebarOpen} onClose={closeSidebar} />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="relative z-20 border-b border-border bg-background/94 pt-[env(safe-area-inset-top)] backdrop-blur-md">
          <div className="flex min-h-[3.5rem] items-center gap-3 px-3 sm:px-5 lg:min-h-[4.5rem] lg:px-7">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="touch-target flex shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground lg:hidden"
            aria-label="Open menu"
          >
            <Menu size={20} aria-hidden />
          </button>
          <span className="flex min-w-0 flex-1 items-center gap-2 lg:hidden">
            <BrandMark size={32} />
            <span className="truncate font-display text-sm font-semibold text-foreground">
              The Real MCU
            </span>
          </span>
          <div className="hidden w-full max-w-2xl flex-1 lg:block">
            <SearchBar />
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="touch-target hidden items-center gap-2 rounded-md border border-input bg-card px-3 text-sm font-semibold text-muted-foreground hover:border-ring hover:text-foreground sm:flex"
              aria-label="Open command palette"
            >
              <Command className="h-4 w-4" aria-hidden />
              <span className="hidden xl:inline">Commands</span>
              <kbd className="hidden rounded-sm bg-muted px-1.5 py-0.5 font-mono text-[0.625rem] text-muted-foreground md:inline">⌘K</kbd>
            </button>
            {isAdmin && (
              <Button asChild size="sm" className="hidden sm:inline-flex">
                <Link to="/collection/add"><Plus aria-hidden /> Add a disc</Link>
              </Button>
            )}
          </div>
          </div>
        </header>

        <OfflineBanner />

        <main id="main-content" className="min-h-0 flex-1 overflow-y-auto pb-[calc(4.5rem+env(safe-area-inset-bottom))] lg:pb-0" tabIndex={-1}>
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </main>
      </div>

      {/* §9.3's "floating chat button on every page". On the shell rather than on each
          page, which is what "every page" means — and it hides itself on the chat. */}
      <FloatingChatButton />

      {/* Batch S3, snag 1. Search left the mobile header's second row — a permanent band
          of chrome above every page, on the smallest screen — and became a slot in the
          bottom bar. It opens here as a sheet so the whole results list has room, rather
          than a dropdown pinned under a 44px strip.

          `mcu:focus-search` is Batch 36's own event, already how `/` focuses the search
          box on a keyboard; reusing it means the sheet does not need `SearchBar` to grow
          an `autoFocus` prop that only one caller would ever pass. */}
      {searchOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close search"
            className="absolute inset-0 cursor-default bg-brand-ink/70 backdrop-blur-[2px]"
            onClick={() => setSearchOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Search the archive"
            className="absolute inset-x-0 top-0 border-b border-border bg-background px-3 pb-3 pt-[calc(env(safe-area-inset-top)+0.75rem)] shadow-lift"
          >
            <div className="flex items-center gap-2">
              <div className="min-w-0 flex-1">
                <SearchBar />
              </div>
              <button
                type="button"
                onClick={() => setSearchOpen(false)}
                className="touch-target shrink-0 rounded-md px-2 text-sm font-semibold text-muted-foreground hover:text-foreground"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <MobileTabBar
        onOpenMenu={() => setSidebarOpen(true)}
        onOpenSearch={() => {
          setSearchOpen(true)
          requestAnimationFrame(() => window.dispatchEvent(new Event('mcu:focus-search')))
        }}
      />

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} isAdmin={isAdmin} />
      <ShortcutsHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} isAdmin={isAdmin} />
    </div>
  )
}
