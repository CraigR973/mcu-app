import { ProfileAvatar } from '@/components/ProfileAvatar'
import { useEffect, useState, type ReactNode } from 'react'
import { flushSync } from 'react-dom'
import { useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Bot, Command, Plus } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import CommandPalette from '@/components/CommandPalette'
import ShortcutsHelpModal from '@/components/ShortcutsHelpModal'
import ErrorBoundary from '@/components/ErrorBoundary'
import OfflineBanner from '@/components/OfflineBanner'
import OutOfDateBanner from '@/components/OutOfDateBanner'
import { PushHealthBanner } from '@/components/PushHealthBanner'
import SearchBar from '@/components/SearchBar'
import { useAuth } from '@/context/auth'
import { useGoBack } from '@/hooks/useGoBack'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { startAutoFlush } from '@/lib/sync'
import { MobileTabBar } from './MobileTabBar'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/brand/BrandMark'
import { isTopLevel, parentPath, titleForPath, YOU_ITEM } from '@/lib/nav-items'
import { usePageChromeTitle } from './page-chrome'
import { PageChromeProvider } from './PageChromeProvider'

interface Props {
  children: ReactNode
}

const ASSISTANT_PATH = '/assistant'

/**
 * The assistant, from the top bar — Batch U3, `DECISIONS.md` #221.
 *
 * **It replaces §9.3's floating chat button.** Fixed over the page's bottom-right corner,
 * that button sat on whatever control scrolled under it: the "Upcoming releases" switch in
 * Settings, a button on Price alerts. A sixth bottom tab would break the five Craig chose
 * (#201), so the way in moved up here, beside the person's initial, where nothing scrolls
 * under it. It shows on every page of the shell, the chat itself included, and marks it.
 */
function AssistantLink({ className }: { className: string }) {
  const { pathname } = useLocation()
  const here = pathname === ASSISTANT_PATH || pathname.startsWith(`${ASSISTANT_PATH}/`)
  return (
    <Link
      to={ASSISTANT_PATH}
      aria-label="Ask the assistant"
      aria-current={here ? 'page' : undefined}
      className={className}
    >
      <Bot className="h-5 w-5 shrink-0" aria-hidden />
      <span className="hidden xl:inline">Assistant</span>
    </Link>
  )
}

/**
 * The phone's top bar — Batch T3, `DECISIONS.md` #201.
 *
 * **The page's name, where the app's name used to be.** A back arrow on anything below a
 * destination, and the person's initial, which opens the "You" page: everything the five
 * bottom tabs do not carry. It replaces the slide-out menu, and the menu button with it.
 * Since Batch U3 the assistant sits beside the initial.
 *
 * The back arrow goes back through history when there is some, and otherwise to the
 * page's parent — a page opened from a notification or a shared link has nowhere to go
 * "back" to, and `navigate(-1)` would leave the app. Since Batch V1 every page but the four
 * bottom tabs and You has one, and a page the You page lists falls back to You.
 */
function PhoneTopBar({ onOpenPalette }: { onOpenPalette: () => void }) {
  const { pathname } = useLocation()
  const goBack = useGoBack(parentPath(pathname))
  const { profile } = useAuth()
  const announced = usePageChromeTitle()
  const title = announced ?? titleForPath(pathname) ?? 'The Real MCU'
  const subPage = !isTopLevel(pathname)

  return (
    <div className="flex min-h-[3.5rem] items-center gap-2 px-3 sm:px-5 lg:hidden">
      {subPage ? (
        <button
          type="button"
          onClick={goBack}
          className="touch-target -ml-1 flex shrink-0 items-center justify-center rounded-md text-foreground hover:bg-muted"
          aria-label="Back"
        >
          <ArrowLeft size={20} aria-hidden />
        </button>
      ) : (
        <BrandMark size={28} />
      )}
      {/* A heading only when the page announced it: that page's own heading is hidden on
          a phone. A page that did not announce one keeps its own, so this stays text. */}
      {announced ? (
        <h1 className="min-w-0 flex-1 truncate font-display text-lg font-semibold text-foreground">{title}</h1>
      ) : (
        <p className="min-w-0 flex-1 truncate font-display text-lg font-semibold text-foreground">{title}</p>
      )}
      <button
        type="button"
        onClick={onOpenPalette}
        className="touch-target hidden shrink-0 items-center justify-center rounded-md text-foreground hover:bg-muted sm:flex"
        aria-label="Open command palette"
      >
        <Command className="h-4 w-4" aria-hidden />
      </button>
      <AssistantLink className="touch-target flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-foreground hover:bg-muted aria-[current=page]:bg-primary/10 aria-[current=page]:text-primary" />
      <Link
        to={YOU_ITEM.path}
        aria-label="You: every other page, and your account"
        aria-current={pathname === YOU_ITEM.path ? 'page' : undefined}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-secondary font-display text-sm font-semibold text-secondary-foreground ring-offset-background aria-[current=page]:ring-2 aria-[current=page]:ring-primary"
      >
        <ProfileAvatar profileId={profile?.id} name={profile?.displayName} className="h-11 w-11" />
      </Link>
    </div>
  )
}

export default function AppLayout({ children }: Props) {
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const queryClient = useQueryClient()
  const { profile } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const location = useLocation()

  // Batch T2, snag 6. Picking a result navigates, and the sheet has to go with it: it used
  // to stay over the film, dimmed, until somebody found Cancel. Keyed on the location's
  // `key`, not its path, so picking the film already on screen still closes it.
  useEffect(() => {
    setSearchOpen(false)
  }, [location.key])

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
    <PageChromeProvider>
    <div className="flex h-[100dvh] min-h-0 overflow-hidden bg-background text-foreground">
      <a href="#main-content" className="fixed left-3 top-3 z-[100] -translate-y-24 rounded-md bg-primary px-4 py-2.5 font-semibold text-primary-foreground shadow-lift focus:translate-y-0">Skip to content</a>
      <Sidebar />

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* AA1: keep the iOS clock and page on the same surface, with a clear rule below. */}
        <header aria-label="Top bar" className="relative z-20 border-b border-border bg-background pt-[env(safe-area-inset-top)]">
          <PhoneTopBar onOpenPalette={() => setPaletteOpen(true)} />
          <div className="hidden min-h-[4.5rem] items-center gap-3 px-7 lg:flex">
          <div className="w-full max-w-2xl flex-1">
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
              <kbd className="hidden rounded-sm bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground md:inline">⌘K</kbd>
            </button>
            {/* Batch U3. The floating button floated here too, over the page's corner; its
                replacement is the same top-bar link at every width. */}
            <AssistantLink className="touch-target flex items-center gap-2 rounded-md border border-input bg-card px-3 py-0.5 text-sm font-semibold text-muted-foreground hover:border-ring hover:text-foreground aria-[current=page]:border-primary/30 aria-[current=page]:bg-primary/10 aria-[current=page]:text-primary" />
            {/* Batch S4. The `isAdmin &&` is gone with #155, and `hidden sm:inline-flex`
                stays on purpose: below 640px the bottom bar carries the add slot, so a
                second one here would be two controls for one job in the scarcest space
                the app has. Snag 7 was that the phone had *neither*. */}
            <Button asChild size="sm" className="hidden sm:inline-flex">
              <Link to="/collection/add"><Plus aria-hidden /> Add a disc</Link>
            </Button>
          </div>
          </div>
        </header>

        <OfflineBanner />
        {/* Batch X8: a screen met an API newer than this build. */}
        <OutOfDateBanner />
        {/* Batch X3: mends this phone's notifications on open; says when they stopped. */}
        <PushHealthBanner />

        <main id="main-content" className="min-h-0 flex-1 overflow-y-auto pb-[calc(4.5rem+env(safe-area-inset-bottom))] lg:pb-0" tabIndex={-1}>
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </main>
      </div>

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
            // Search covers the top bar, so its surface follows AA1's bar colour.
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

      {/* Batch W1, snag 1. iOS raises the keyboard only for a focus made while the tap is
          still being handled. This used to focus the box an animation frame later, so an
          iPhone needed a second tap on it. `flushSync` builds the sheet now, inside the tap,
          and the box is focused before the handler returns. */}
      <MobileTabBar
        onOpenSearch={() => {
          flushSync(() => setSearchOpen(true))
          window.dispatchEvent(new Event('mcu:focus-search'))
        }}
      />

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} isAdmin={isAdmin} />
      <ShortcutsHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} isAdmin={isAdmin} />
    </div>
    </PageChromeProvider>
  )
}
