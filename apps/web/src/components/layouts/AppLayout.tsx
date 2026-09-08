import { useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Menu } from 'lucide-react'
import Sidebar from './Sidebar'
import ErrorBoundary from '@/components/ErrorBoundary'
import OfflineBanner from '@/components/OfflineBanner'
import SearchBar from '@/components/SearchBar'
import { startAutoFlush } from '@/lib/sync'

interface Props {
  children: ReactNode
}

export default function AppLayout({ children }: Props) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const queryClient = useQueryClient()

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
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex items-center gap-3 border-b border-border px-4 py-2">
          <button
            onClick={() => setSidebarOpen(true)}
            className="shrink-0 text-muted-foreground hover:text-foreground lg:hidden"
            aria-label="Open menu"
          >
            <Menu size={20} />
          </button>
          <span className="shrink-0 font-semibold text-sm lg:hidden">The Real MCU</span>
          <div className="flex-1 max-w-md">
            <SearchBar />
          </div>
        </header>

        <OfflineBanner />

        <main className="flex-1 overflow-y-auto">
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}
